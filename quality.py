"""Fail-closed public evidence policy; never tests authenticated proxy health."""
import datetime as dt
from decimal import Decimal, InvalidOperation

POLICY = dict(version='strict-evidence-v1', measurement_max_seconds=86400,
              fetch_max_seconds=86400, conflict_policy='all observations must pass',
              loss_unit='ratio', speed_unit='MB/s', require_probe_viewpoint=True,
              require_measurement_time=True, loss_required=0, speed_required='finite > 0',
              packet_evidence='finite integers sent>0 and received=sent; packets units',
              require_source_state='fresh', fallback_padding=False,
              authenticated_proxy_health='not tested')


def age(value, now):
    try:
        a=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        b=dt.datetime.fromisoformat(now.replace('Z','+00:00'))
        if a.tzinfo is None or b.tzinfo is None: return None
        return (b-a).total_seconds()
    except (TypeError, ValueError, AttributeError): return None


def observation_reasons(p, now, source):
    reasons=[]
    for key,label,unit in [('loss','loss','ratio'),('download_speed','speed','MB/s')]:
        metric=p.get('metrics',{}).get(key,{})
        raw=metric.get('value')
        try: value=Decimal(str(raw)) if not isinstance(raw,bool) else Decimal('NaN')
        except (InvalidOperation,TypeError,ValueError): value=Decimal('NaN')
        if not value.is_finite(): reasons.append('unknown_'+label)
        elif value<0 or (key=='loss' and value>1): reasons.append('invalid_'+label)
        elif key=='loss' and value>0: reasons.append('positive_loss')
        elif key=='download_speed' and value==0: reasons.append('zero_speed')
        if metric.get('unit')!=unit: reasons.append('unknown_'+label+'_unit')
    for key,limit in [('measurement_time',POLICY['measurement_max_seconds']),('fetched_at',POLICY['fetch_max_seconds'])]:
        seconds=age(p.get(key),now)
        if seconds is None: reasons.append('unknown_'+key)
        elif seconds<0: reasons.append('future_'+key)
        elif seconds>limit: reasons.append('stale_'+key)
    packets=[]
    for key in ('sent','received'):
        m=p.get('metrics',{}).get(key,{})
        raw=m.get('value')
        try: value=Decimal(str(raw)) if not isinstance(raw,bool) else Decimal('NaN')
        except (InvalidOperation,TypeError,ValueError): value=Decimal('NaN')
        packets.append(value)
        if m.get('unit')!='packets' or not value.is_finite() or value<0 or value!=value.to_integral_value():
            reasons.append('invalid_packet_evidence')
    sent,received=packets
    if not (sent.is_finite() and received.is_finite() and sent>0 and received==sent):
        reasons.append('invalid_packet_evidence')
    viewpoint=p.get('probe_viewpoint')
    if not isinstance(viewpoint,str) or viewpoint.strip().lower() in ('','unknown','n/a','none','null','-'):
        reasons.append('unknown_probe_viewpoint')
    if source.get('state')!='fresh': reasons.append('source_not_fresh')
    return sorted(set(reasons))


def evaluate(records, now, sources):
    """Conservative unanimity, not mirror voting or best-observation selection."""
    for record in records:
        reasons=set()
        for p in record['provenance']:
            excluded=observation_reasons(p,now,sources.get(p['source_id'],{}))
            p['quality']=dict(eligible=not excluded,reasons=excluded)
            reasons.update(excluded)
        if not record['provenance']: reasons.add('no_observations')
        record['quality']=dict(policy_version=POLICY['version'],eligible=not reasons,
                               reasons=sorted(reasons),authenticated_proxy_health='not tested')
    return records
