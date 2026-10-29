"""Publication allowlist and dataset consistency gate (not a substitute for Gitleaks)."""
import hashlib
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

HOSTS={'github.com','raw.githubusercontent.com','api.github.com','www.cloudflare.com',
       'ip.164746.xyz','cf.090227.xyz','www.wetest.vip','byoip.top','example.com'}
ROOT_FILES={'aggregate.py','pipeline.py','quality.py','audit.py','README.md','QUALITY-POLICY.md','LICENSE','DATA-NOTICE.md','.gitignore'}

def file_limit(name):
    # Full dual-stack metric tables carry all observations, not only ten rows.
    return 16000000 if name in {'data/candidates.json','data/last-good-candidates.json','data/records.json'} else 2000000

def check_text(name,text):
    patterns=[r'(?:vless|vmess|trojan|ss)://',r'[a-z0-9]{8}-(?:[a-z0-9]{4}-){3}[a-z0-9]{12}',
              r'/' + r'root/',r'-----BEGIN (?:\w+ )?PRIVATE KEY-----',r'gh[pousr]_[A-Za-z0-9]{20,}',
              r'https?://[^\s<>\)"\']*[?&](?:token|key|uuid|password|path)=']
    if any(re.search(p,text,re.I) for p in patterns): raise ValueError('sensitive field: '+name)
    for url in re.findall(r'https?://[^\s<>\)"\'`]+',text):
        parsed=urlsplit(url)
        if parsed.hostname not in HOSTS or parsed.username or parsed.password:
            raise ValueError('unapproved URL host: '+name)

def check_data(root):
    status=json.loads((root/'status.json').read_text())
    if not (root/'records.json').exists():
        if status['usable']: raise ValueError('usable without data')
        return
    obj=json.loads((root/'records.json').read_text());records=obj['records']
    keys=[(r['address'],r['port']) for r in records]
    if len(keys)!=len(set(keys)): raise ValueError('duplicate records')
    for r in records:
        ip=ipaddress.ip_address(r['address'])
        if '%' in r['address'] or not ip.is_global or ip.is_multicast or ip.version!=r['family'] or not r['provenance']:
            raise ValueError('invalid record')
        if status['usable']:
            from aggregate import valid_address,parse_ranges
            nets=parse_ranges('\n'.join(status['cloudflare_ranges']['networks'][str(r['family'])]),r['family'])
            if not valid_address(r['address'],r['family'],nets): raise ValueError('retained record outside current CF ranges')
            from pipeline import timestamp
            if timestamp(status['dataset_valid_until']) < timestamp(status.get('completed_at',status['attempted_at'])):
                raise ValueError('usable expired dataset')
        if r['category']!='general': raise ValueError('unsupported carrier category')
    if status.get('schema_version')==2:
        from quality import evaluate, POLICY
        candidates=json.loads((root/'candidates.json').read_text())['records']
        if status['policy_version']!=POLICY['version']: raise ValueError('policy mismatch')
        for name,digest in status['file_sha256'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest: raise ValueError('hash mismatch '+name)
        for family in (4,6):
            subset=[r for r in candidates if r['family']==family]
            if len(subset)!=status['candidate_counts'][f'all-v{family}']: raise ValueError('candidate count')
            expected=[r['address'] if r['port'] is None else
                (f"[{r['address']}]" if family==6 else r['address'])+':'+str(r['port']) for r in subset]
            if (root/f'candidates-v{family}.txt').read_text().splitlines()!=expected: raise ValueError('candidate output mismatch')
            if (root/f'recommended-v{family}.txt').read_bytes()!=(root/f'all-v{family}.txt').read_bytes(): raise ValueError('recommended alias')
        keys=[(r['address'],r['port']) for r in candidates]
        if len(keys)!=len(set(keys)): raise ValueError('duplicate candidates')
        import copy
        evaluated=evaluate(copy.deepcopy(candidates),status['completed_at'],status['sources'])
        if not status['collection_ok']:
            for r in evaluated:
                r['quality']['eligible']=False
                r['quality']['reasons']=sorted(set(r['quality']['reasons']+['collection_unavailable']))
        for expected,actual in zip(evaluated,candidates):
            if expected['quality']!=actual['quality'] or any(a['quality']!=b['quality'] for a,b in zip(expected['provenance'],actual['provenance'])):
                raise ValueError('quality reason mismatch')
        allowed=[r for r in evaluated if r['quality']['eligible']]
        if allowed!=records: raise ValueError('recommended content mismatch')
        if [(r['address'],r['port']) for r in allowed]!=[(r['address'],r['port']) for r in records]:
            raise ValueError('recommendation eligibility mismatch')
        if bool(records)!=status['usable']: raise ValueError('usable mismatch')
        from collections import Counter
        observations=dict(Counter(reason for r in candidates for p in r['provenance'] for reason in p['quality']['reasons']))
        if observations!=status['observation_exclusion_reasons']: raise ValueError('observation reason counts')
        if obj['valid_until']!=status['recommendation_valid_until']: raise ValueError('recommendation expiry mismatch')
        if records:
            from pipeline import timestamp
            deadlines=[timestamp(p[key])+__import__('datetime').timedelta(seconds=POLICY[limit])
                for r in records for p in r['provenance'] for key,limit in
                [('fetched_at','fetch_max_seconds'),('measurement_time','measurement_max_seconds')]]
            if timestamp(status['recommendation_valid_until'])>min(deadlines): raise ValueError('extended recommendation expiry')
        reasons=dict(Counter(reason for r in candidates if not r['quality']['eligible'] for reason in r['quality']['reasons']))
        if reasons!=status['exclusion_reasons'] or status['excluded_records']!=len(candidates)-len(records):
            raise ValueError('exclusion counts')
        for r in candidates:
            ip=ipaddress.ip_address(r['address'])
            if not ip.is_global or ip.is_multicast or ip.version!=r['family'] or not r['provenance']:
                raise ValueError('invalid candidate')
    for name,count in status['counts'].items():
        file=root/(name+'.txt');text=file.read_text()
        lines=text.splitlines()
        family=int(name[-1]);category=name.split('-')[0]
        expected=[r['address'] if r['port'] is None else
            (f"[{r['address']}]" if family==6 else r['address'])+':'+str(r['port'])
            for r in records if r['family']==family and (category=='all' or r['category']==category)]
        if lines!=expected or len(lines)!=count or len(lines)!=len(set(lines)):
            raise ValueError('count/order mismatch '+name)
        if hashlib.sha256(file.read_bytes()).hexdigest()!=status['file_sha256'][file.name]:
            raise ValueError('hash mismatch '+name)

def main():
    root=Path(__file__).parent
    files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '.git' in p.parts or '__pycache__' in p.parts: continue
        rel=p.relative_to(root).as_posix()
        allowed=(rel in ROOT_FILES or re.fullmatch(r'tests/test_[a-z_]+\.py',rel) or
                 rel=='.github/workflows/update.yml' or rel=='notices/IPDB-LICENSE.txt' or
                 re.fullmatch(r'data/(?:records|candidates|last-good-candidates|policy|sources|status)\.json',rel) or
                 re.fullmatch(r'data/(?:all|general|cmcc|cu|ct|candidates|recommended)-v[46]\.txt',rel))
        if not allowed or p.is_symlink() or p.stat().st_size>file_limit(rel): raise ValueError('unapproved file '+rel)
        # Negative secret fixtures are synthetic strings, not publication inputs.
        if not rel.startswith('tests/'): check_text(rel,p.read_text())
        files.append(rel)
    if (root/'data/status.json').exists():check_data(root/'data')
    print(json.dumps({'public_files':files,'file_count':len(files),'boundary':'pass'},sort_keys=True))

if __name__=='__main__':main()
