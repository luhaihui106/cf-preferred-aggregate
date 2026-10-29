"""Bounded fetch and freshness-aware publication for the fixed source catalogue."""
import argparse
import datetime as dt
import hashlib
import json
from decimal import Decimal, InvalidOperation
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from quality import evaluate, POLICY

IPDB_LICENSE = (Path(__file__).parent/'notices/IPDB-LICENSE.txt').read_text()
STALE_SECONDS = 86400
SOURCES = [dict(id=f'ipdb-v{v}', provider_id='ipdb', family=v, path=f'BestCF/ipv{v}.csv',
    shortlist_path=f'BestCF/bestcfv{v}.txt', parser='ipdb',
    url=f'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv{v}.txt',
    origin='https://github.com/ymyuuu/IPDB',kind='published_metric_table_with_shortlist',
    terms_decision='repository MIT with original notice; underlying data rights not warranted',
    carrier='general') for v in (4,6)] + [dict(
    id='cf-speed-dns-v4',provider_id='cf-speed-dns',family=4,parser='comma',
    url='https://ip.164746.xyz/ipTop10.html',origin='https://github.com/ZhiXuanWang/cf-speed-dns',
    kind='published_preferred_shortlist',carrier='general',
    terms_decision='documented minimal factual result interface; attributed limited reuse, no blanket data license'
)] + [dict(id=f'cmliussss-{carrier}',provider_id='cmliussss',family=4,parser='lines',
    url=f'https://cf.090227.xyz/{carrier}',origin='https://cf.090227.xyz/',
    kind='provider_labelled_candidates',carrier=carrier,
    terms_decision='documented public minimal IP API; attributed limited factual reuse, data license unknown'
) for carrier in ('cmcc','cu','ct')]

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect refused')

def fetch_text(url,max_bytes=512000):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('HTTPS without credentials required')
    opener=urllib.request.build_opener(NoRedirect())
    deadline=time.monotonic()+25
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'cf-preferred-aggregate/1.0','Accept-Encoding':'identity'})
            with opener.open(req,timeout=min(10,max(.1,deadline-time.monotonic()))) as r:
                if r.status!=200: raise ValueError('HTTP status rejected')
                if int(r.headers.get('Content-Length','0'))>max_bytes: raise ValueError('body too large')
                chunks=[];total=0
                while True:
                    if time.monotonic()>deadline: raise TimeoutError('body deadline')
                    chunk=r.read1(min(16384,max_bytes-total+1))
                    if not chunk: break
                    total+=len(chunk)
                    if total>max_bytes: raise ValueError('body too large')
                    chunks.append(chunk)
                return b''.join(chunks).decode('utf-8-sig',errors='strict')
        except (OSError,urllib.error.URLError):
            if attempt or time.monotonic()>=deadline: raise
    raise TimeoutError('fetch failed')

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def timestamp(s): return dt.datetime.fromisoformat(s.replace('Z','+00:00'))
def dump(path,obj):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)
def recent(value,now):
    try: return 0 <= (timestamp(now)-timestamp(value)).total_seconds() <= STALE_SECONDS
    except (TypeError,ValueError,AttributeError): return False

def summarize_quality(rows):
    """Descriptive only: distinguish unparseable metrics from measured nonzero."""
    def numbers(key):
        values=[]
        for row in rows:
            try: value=Decimal(str(row['metrics'][key]['value']))
            except (InvalidOperation,TypeError,ValueError): value=None
            values.append(value if value is not None and value.is_finite() and value>=0 else None)
        return values
    loss=numbers('loss');speed=numbers('download_speed')
    return dict(scope='validated collected candidates',
        nonzero_loss_rows=sum(v is not None and v>0 for v in loss),
        unknown_loss_rows=sum(v is None for v in loss),
        zero_download_rows=sum(v==0 for v in speed),
        unknown_download_rows=sum(v is None for v in speed),
        policy='descriptive candidate counts; default gated by upstream-preferred-v1')


def generate(out,now=None,fetch=fetch_text):
    from aggregate import parse_csv,parse_ranges,valid_address,merge,parse_ip_list,collect_ipdb
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fixed_now=now
    clock=(lambda: fixed_now) if fixed_now else utcnow
    now=clock()
    old={};old_records=[]
    try:
        old=json.loads((out/'status.json').read_text())
        old_records=json.loads((out/('candidates.json' if (out/'candidates.json').exists() else 'records.json')).read_text())['records']
    except (OSError,ValueError,KeyError): pass
    status=dict(schema_version=1,attempted_at=now,state='fresh',published_dataset=False,usable=False,
        stale_max_seconds=STALE_SECONDS,sources={},counts=old.get('counts',{}),
        dataset_generated_at=old.get('dataset_generated_at'),dataset_valid_until=old.get('dataset_valid_until'),
        file_sha256=old.get('file_sha256',{}),adapter_count=len(SOURCES),
        provider_count=len({s['provider_id'] for s in SOURCES}),fresh_provider_count=0,
        contributing_provider_count=0)
    ranges={}
    try:
        for family in (4,6): ranges[family]=parse_ranges(fetch(f'https://www.cloudflare.com/ips-v{family}'),family)
        status['cloudflare_ranges']=dict(state='fresh',fetched_at=clock(),networks={str(k):[str(n) for n in v] for k,v in ranges.items()})
    except Exception as e:
        status.update(state='range_unavailable',error=type(e).__name__)
        return publish(out,status,old_records,now,False)
    revision=None
    try:
        meta=json.loads(fetch('https://api.github.com/repos/ymyuuu/IPDB/commits/main'))
        revision=meta['sha']
        if not re.fullmatch('[0-9a-f]{40}',revision): raise ValueError('invalid revision')
        if fetch(f'https://raw.githubusercontent.com/ymyuuu/IPDB/{revision}/LICENSE').strip()!=IPDB_LICENSE.strip():
            raise ValueError('upstream license changed')
    except Exception: revision=None
    groups=[];fresh=0
    for source in SOURCES:
        sid=source['id'];prev=old.get('sources',{}).get(sid,{})
        state={**source,'state':'error','attempted_at':now,'fetched_at':prev.get('fetched_at'),
            'measurement_time':None,'source_revision':prev.get('source_revision'),
            'source_published_at':prev.get('source_published_at'),'accepted_rows':0,'rejected_rows':0,
            'input_rows':0,'preferred_rows':0,'quality_summary':None,'selection_policy':
                'full CSV with same-revision shortlist annotation v2' if source['parser']=='ipdb' else 'entire bounded minimal published feed'}
        rows=[]
        try:
            if source['parser']=='ipdb':
                if not revision: raise ValueError('revision or license unavailable')
                base=f'https://raw.githubusercontent.com/ymyuuu/IPDB/{revision}/'
                url=base+source['shortlist_path']
                csv_text=fetch(base+source['path'])
                parsed=collect_ipdb(csv_text,fetch(url),source['family'])
                state['input_rows']=len(parse_csv(csv_text))
                state.update(source_revision=revision,source_published_at=meta['commit']['committer']['date'],
                             metrics_url=base+source['path'])
            else:
                url=source['url']
                parsed=parse_ip_list(fetch(url),separator=source['parser'],claim=source['carrier'])
                state.update(input_rows=len(parsed),source_revision=None,source_published_at=None)
            state['preferred_rows']=len({r['shortlist_rank'] for r in parsed if r.get('shortlist_rank') is not None}) if source['parser']=='ipdb' else len(parsed)
            for row in parsed:
                ip=valid_address(row['address'],source['family'],ranges[source['family']])
                if not ip: state['rejected_rows']+=1;continue
                rows.append({**row,'address':ip,'fetched_at':now,'source_revision':state['source_revision'],
                             'provider_id':source['provider_id'],'origin':source['origin'],'endpoint_url':url})
            if not rows: raise ValueError('no validated results')
            if source['parser']=='ipdb':
                state['quality_summary']=summarize_quality(rows)
            fetched_at=clock()
            for row in rows: row['fetched_at']=fetched_at
            state.update(state='fresh',fetched_at=fetched_at,resolved_url=url)
            fresh+=1
        except Exception as e:
            rows=[]  # Never publish half a parse/validation as fresh or retained data.
            state['error']=type(e).__name__
            if isinstance(e,urllib.error.HTTPError): state['http_status']=e.code
            compatible=source['parser']!='ipdb' or prev.get('selection_policy')==state['selection_policy']
            if recent(prev.get('fetched_at'),now) and compatible:
                for field in ('source_revision','source_published_at','resolved_url','metrics_url','input_rows','preferred_rows','quality_summary'):
                    if field in prev: state[field]=prev[field]
                for record in old_records:
                    for p in record['provenance']:
                        if p['source_id']==sid and valid_address(p['address'],source['family'],ranges[source['family']]):
                            rows.append({k:v for k,v in p.items() if k!='source_id'})
                rows.sort(key=lambda r:r['rank'])
                if rows: state['state']='stale'
            elif prev.get('fetched_at'): state['state']='expired'
        state['accepted_rows']=len(rows)
        status['sources'][sid]=state;groups.append((sid,rows))
    completed_at=clock()
    status['completed_at']=completed_at
    # A slow attempt must not extend an old source beyond its original TTL.
    for index,(sid,rows) in enumerate(groups):
        state=status['sources'][sid]
        if state['state']=='stale' and not recent(state['fetched_at'],completed_at):
            state.update(state='expired',accepted_rows=0)
            groups[index]=(sid,[])
    status['fresh_provider_count']=len({s['provider_id'] for s in status['sources'].values() if s['state']=='fresh'})
    status['contributing_provider_count']=len({s['provider_id'] for s in status['sources'].values() if s['accepted_rows']})
    if not fresh:
        # Judge the retained snapshot, not adapters that never contributed to it.
        retained_ids={p['source_id'] for r in old_records for p in r['provenance']}
        retained_sources_valid=bool(retained_ids) and all(
            status['sources'].get(sid,{}).get('state')=='stale' for sid in retained_ids)
        try:
            within_snapshot_ttl=timestamp(completed_at)<=timestamp(old.get('dataset_valid_until'))
        except (TypeError,ValueError,AttributeError): within_snapshot_ttl=False
        status['usable']=bool(old_records) and retained_sources_valid and within_snapshot_ttl
        status['state']='stale' if status['usable'] else 'expired'
        retained_valid=all(valid_address(r['address'],r['family'],ranges[r['family']]) for r in old_records)
        if old_records and not retained_valid:
            status.update(state='range_changed',usable=False)
        return publish(out,status,old_records,completed_at,False)
    records=merge(groups)
    # A failed/expired conflicting source must not vanish and thereby promote
    # the same endpoint via a surviving source. Keep its observation as a veto,
    # not as a current candidate supplier or an independent vote.
    previous={(r['address'],r['port']):r for r in old_records}
    for record in records:
        seen_sources={p['source_id'] for p in record['provenance']}
        for p in previous.get((record['address'],record['port']),{}).get('provenance',[]):
            sid=p['source_id']
            if sid not in seen_sources and status['sources'].get(sid,{}).get('state')!='fresh':
                record['provenance'].append(p)
        claims=sorted({p['carrier_claim'] for p in record['provenance'] if p['carrier_claim']!='general'})
        record.update(carrier_claims=claims,carrier_conflict=len(claims)>1)
    valid_until=min(timestamp(s['fetched_at'])+dt.timedelta(seconds=STALE_SECONDS) for s in status['sources'].values() if s['accepted_rows'])
    status.update(state='fresh' if all(s['state']=='fresh' for s in status['sources'].values()) else 'partial',
        published_dataset=True,usable=True,dataset_generated_at=completed_at,
        dataset_valid_until=valid_until.isoformat(timespec='seconds').replace('+00:00','Z'))
    return publish(out,status,records,completed_at,True)

def publish(out,status,records,now,new_dataset):
    """Separate current recommendations from retained forensic candidates."""
    from collections import Counter

    status['schema_version']=3
    status['policy_version']=POLICY['version']
    status['completed_at']=now
    status['collection_ok']=new_dataset
    status['candidate_usable']=bool(new_dataset or status.get('usable'))
    evaluate(records,now,status['sources'])
    if not new_dataset:
        for r in records:
            r['quality']['eligible']=False
            r['quality']['reasons']=sorted(set(r['quality']['reasons']+['collection_unavailable']))
    recommended=[r for r in records if r['quality']['eligible']]
    status['usable']=bool(recommended)
    status['recommendation_state']=('upstream-preferred' if status['state']=='fresh' else 'degraded') if recommended else (
        'expired' if status['state'] in ('expired','range_changed') else 'degraded' if not new_dataset or status['state']!='fresh' else 'empty')
    status['candidate_counts']={};status['counts']={};status['file_sha256']={}
    status['excluded_records']=len(records)-len(recommended)
    status['exclusion_reasons']=dict(sorted(Counter(reason for r in records if not r['quality']['eligible'] for reason in r['quality']['reasons']).items()))
    status['observation_exclusion_reasons']=dict(sorted(Counter(reason for r in records for p in r['provenance'] for reason in p['quality']['reasons']).items()))
    status['quality_warnings']=dict(sorted(Counter(warning for r in records for warning in r['quality']['warnings']).items()))
    status['quality_level']='upstream-preferred/unverified'
    status['independently_verified_records']=0
    status['recommended_provider_count']=len({p['provider_id'] for r in recommended for p in r['provenance'] if p['quality']['eligible'] and p.get('provider_id')})
    for sid,source in status['sources'].items():
        observations=[p for r in records for p in r['provenance'] if p['source_id']==sid]
        source['recommended_observations']=sum(p['quality']['eligible'] for p in observations) if new_dataset else 0
        source['default_eligible_records']=sum(r['quality']['eligible'] and any(p['source_id']==sid and p['quality']['eligible'] for p in r['provenance']) for r in records) if new_dataset else 0
        source['quality_warnings']=dict(sorted(Counter(w for p in observations for w in p['quality']['warnings']).items()))
        source['exclusion_reasons']=dict(sorted(Counter(reason for p in observations for reason in p['quality']['reasons']).items()))
    def write_txt(name,selected):
        text=''.join((r['address'] if r['port'] is None else
            (f"[{r['address']}]" if r['family']==6 else r['address'])+':'+str(r['port']))+'\n' for r in selected)
        (out/(name+'.txt')).write_text(text,encoding='utf-8')
    for family in (4,6):
        candidates=[r for r in records if r['family']==family]
        write_txt(f'candidates-v{family}',candidates)
        status['candidate_counts'][f'all-v{family}']=len(candidates)
        for category in ('all','general','cmcc','cu','ct'):
            name=f'{category}-v{family}'
            selected=[r for r in recommended if r['family']==family and (category=='all' or r['category']==category)]
            write_txt(name,selected)
            status['counts'][name]=len(selected)
        write_txt(f'recommended-v{family}',[r for r in recommended if r['family']==family])
    envelope=dict(schema_version=3,policy_version=POLICY['version'],generated_at=now,
        valid_until=status.get('dataset_valid_until'),ordering='catalogue round-robin; original source ranks',records=records)
    dump(out/'candidates.json',envelope)
    if new_dataset and status['state']=='fresh': dump(out/'last-good-candidates.json',envelope)

    deadlines=[timestamp(now)+dt.timedelta(seconds=STALE_SECONDS)]
    for r in recommended:
        for p in r['provenance']:
            deadlines.append(timestamp(p['fetched_at'])+dt.timedelta(seconds=POLICY['fetch_max_seconds']))
            if p.get('measurement_time') is not None:
                deadlines.append(timestamp(p['measurement_time'])+dt.timedelta(seconds=POLICY['measurement_max_seconds']))
            if p.get('valid_until') is not None: deadlines.append(timestamp(p['valid_until']))
    status['recommendation_valid_until']=min(deadlines).isoformat(timespec='seconds').replace('+00:00','Z') if recommended else None
    dump(out/'records.json',{**envelope,'valid_until':status['recommendation_valid_until'],'records':recommended})
    dump(out/'policy.json',POLICY)
    dump(out/'sources.json',dict(schema_version=3,attempted_at=status['attempted_at'],sources=list(status['sources'].values())))
    for path in sorted(out.iterdir()):
        if path.suffix in ('.json','.txt') and path.name!='status.json':
            status['file_sha256'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    dump(out/'status.json',status)
    return status


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('data'))
    args=parser.parse_args()
    result=generate(args.output)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    # Status must be committed before CI signals unusable data.
