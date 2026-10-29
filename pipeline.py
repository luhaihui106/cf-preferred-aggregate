"""Bounded fetch and freshness-aware publication for the fixed source catalogue."""
import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

IPDB_LICENSE = (Path(__file__).parent/'notices/IPDB-LICENSE.txt').read_text()
STALE_SECONDS = 86400
SOURCES = [dict(id=f'ipdb-v{v}', family=v, path=f'BestCF/ipv{v}.csv',
    url=f'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/ipv{v}.csv',
    origin='https://github.com/ymyuuu/IPDB',kind='published_results',
    terms_decision='repository MIT with original notice; underlying data rights not warranted',
    carrier='general') for v in (4,6)]

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

def generate(out,now=None,fetch=fetch_text):
    from aggregate import parse_csv,parse_ranges,valid_address,merge
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    fixed_now=now
    clock=(lambda: fixed_now) if fixed_now else utcnow
    now=clock()
    old={};old_records=[]
    try:
        old=json.loads((out/'status.json').read_text())
        old_records=json.loads((out/'records.json').read_text())['records']
    except (OSError,ValueError,KeyError): pass
    status=dict(schema_version=1,attempted_at=now,state='fresh',published_dataset=False,usable=False,
        stale_max_seconds=STALE_SECONDS,sources={},counts=old.get('counts',{}),
        dataset_generated_at=old.get('dataset_generated_at'),dataset_valid_until=old.get('dataset_valid_until'),
        file_sha256=old.get('file_sha256',{}))
    ranges={}
    try:
        for family in (4,6): ranges[family]=parse_ranges(fetch(f'https://www.cloudflare.com/ips-v{family}'),family)
        status['cloudflare_ranges']=dict(state='fresh',fetched_at=clock(),networks={str(k):[str(n) for n in v] for k,v in ranges.items()})
    except Exception as e:
        status.update(state='range_unavailable',error=type(e).__name__)
        dump(out/'status.json',status)
        return status
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
            'source_published_at':prev.get('source_published_at'),'accepted_rows':0,'rejected_rows':0}
        rows=[]
        try:
            if not revision: raise ValueError('revision or license unavailable')
            url=f"https://raw.githubusercontent.com/ymyuuu/IPDB/{revision}/{source['path']}"
            for row in parse_csv(fetch(url)):
                ip=valid_address(row['address'],source['family'],ranges[source['family']])
                if not ip: state['rejected_rows']+=1;continue
                rows.append({**row,'address':ip,'fetched_at':now,'source_revision':revision})
            if not rows: raise ValueError('no validated results')
            fetched_at=clock()
            for row in rows: row['fetched_at']=fetched_at
            state.update(state='fresh',fetched_at=fetched_at,source_revision=revision,
                source_published_at=meta['commit']['committer']['date'],resolved_url=url)
            fresh+=1
        except Exception as e:
            state['error']=type(e).__name__
            if recent(prev.get('fetched_at'),now):
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
    if not fresh:
        status['state']='stale' if all(s['state']=='stale' for s in status['sources'].values()) else 'expired'
        status['usable']=bool(old_records) and all(s['state']=='stale' for s in status['sources'].values())
        retained_valid=all(valid_address(r['address'],r['family'],ranges[r['family']]) for r in old_records)
        if old_records and not retained_valid:
            status.update(state='range_changed',usable=False)
        dump(out/'status.json',status)
        dump(out/'sources.json',dict(schema_version=1,attempted_at=now,sources=list(status['sources'].values())))
        return status
    records=merge(groups)
    valid_until=min(timestamp(s['fetched_at'])+dt.timedelta(seconds=STALE_SECONDS) for s in status['sources'].values() if s['accepted_rows'])
    status.update(state='fresh' if all(s['state']=='fresh' for s in status['sources'].values()) else 'partial',
        published_dataset=True,usable=True,dataset_generated_at=completed_at,
        dataset_valid_until=valid_until.isoformat(timespec='seconds').replace('+00:00','Z'))
    status['counts']={};status['file_sha256']={}
    for family in (4,6):
        for category in ('all','general','cmcc','cu','ct'):
            name=f'{category}-v{family}'
            selected=[r for r in records if r['family']==family and (category=='all' or r['category']==category)]
            def endpoint(r):
                ip=r['address']
                return ip if r['port'] is None else (f'[{ip}]' if family==6 else ip)+':'+str(r['port'])
            text=''.join(endpoint(r)+'\n' for r in selected)
            (out/(name+'.txt')).write_text(text,encoding='utf-8')
            status['counts'][name]=len(selected)
            status['file_sha256'][name+'.txt']=hashlib.sha256(text.encode()).hexdigest()
    dump(out/'records.json',dict(schema_version=1,generated_at=completed_at,valid_until=status['dataset_valid_until'],
        ordering='catalogue source order round-robin; upstream order retained',records=records))
    dump(out/'sources.json',dict(schema_version=1,attempted_at=now,sources=list(status['sources'].values())))
    dump(out/'status.json',status)
    return status

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('data'))
    args=parser.parse_args()
    result=generate(args.output)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    # Status must be committed before CI signals unusable data.
