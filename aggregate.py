"""Original bounded public-result aggregation; no network speed testing."""
import csv
import io
import ipaddress
from pipeline import generate, fetch_text, NoRedirect, IPDB_LICENSE


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    expected = ['IP 地址','已发送','已接收','丢包率','平均延迟','下载速度 (MB/s)']
    if reader.fieldnames != expected:
        raise ValueError('unexpected CSV schema')
    rows = []
    for rank, row in enumerate(reader, 1):
        if rank > 1000:
            raise ValueError('too many source rows')
        if None in row or any(v is None for v in row.values()):
            raise ValueError('invalid CSV row')
        rows.append({'address': row['IP 地址'].strip(), 'port': None, 'rank':rank,
                     'carrier_claim':'general','carrier_verified':False,
                     'measurement_time':None,'probe_viewpoint':None,
                     'metrics':{k:{'value':row[c], 'unit':u} for k,c,u in [
                         ('sent','已发送','packets'),('received','已接收','packets'),
                         ('loss','丢包率','ratio'),('latency','平均延迟',None),
                         ('download_speed','下载速度 (MB/s)','MB/s')]}})
    return rows


def parse_ranges(text, family):
    nets = [ipaddress.ip_network(s.strip(), strict=True) for s in text.splitlines() if s.strip()]
    if not nets or len(nets)>100 or any(n.version!=family or not n.is_global or n.prefixlen < (8 if family==4 else 16) for n in nets):
        raise ValueError('unsafe official range response')
    return nets


def merge(groups):
    """Stable source round-robin; every occurrence retained, no metric sorting."""
    records = {}
    for i in range(max((len(rows) for _, rows in groups), default=0)):
        for source, rows in groups:
            if i >= len(rows):
                continue
            row = rows[i]
            key = (row['address'], row['port'])
            if key not in records:
                records[key] = {'address':key[0], 'port':key[1],
                                'family':ipaddress.ip_address(key[0]).version,
                                'category':'general','provenance':[]}
            records[key]['provenance'].append({'source_id':source, **row})
    for record in records.values():
        claims = sorted({p['carrier_claim'] for p in record['provenance'] if p['carrier_claim']!='general'})
        record['carrier_claims'] = claims
        record['carrier_conflict'] = len(claims)>1
        # Unsupported claims never enter a trustworthy carrier pool.
    return list(records.values())


def valid_address(text, family, nets):
    if '%' in text:
        return None
    try:
        ip = ipaddress.ip_address(text)
        if ip.version == family and ip.is_global and not ip.is_multicast and any(ip in n for n in nets):
            return str(ip)
    except ValueError:
        pass
    return None
