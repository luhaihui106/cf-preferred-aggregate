"""Published preference eligibility, not authenticated proxy verification."""
import datetime as dt
from decimal import Decimal, InvalidOperation

POLICY = dict(version='upstream-preferred-v1', measurement_max_seconds=86400,
              fetch_max_seconds=86400, conflict_policy='any explicit failure vetoes endpoint; at least one published preference required',
              loss_unit='ratio', speed_unit='MB/s', require_probe_viewpoint=False,
              require_measurement_time=False, missing_metrics='unknown warnings, not failures',
              require_source_state='fresh', fallback_padding=False,
              authenticated_proxy_health='not tested')


def age(value, now):
    try:
        a=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        b=dt.datetime.fromisoformat(now.replace('Z','+00:00'))
        if a.tzinfo is None or b.tzinfo is None: return None
        return (b-a).total_seconds()
    except (TypeError, ValueError, AttributeError): return None


def observation_quality(p, now, source):
    reasons=[];warnings=[]
    metrics=p.get('metrics',{})
    values={}
    for key,label,unit in [('loss','loss','ratio'),('download_speed','speed','MB/s'),
                           ('sent','sent','packets'),('received','received','packets'),('latency','latency',None)]:
        metric=metrics.get(key,{})
        raw=metric.get('value')
        if raw is None or (isinstance(raw,str) and not raw.strip()):
            warnings.append('unknown_'+label);values[key]=None;continue
        try: value=Decimal(str(raw)) if not isinstance(raw,bool) else Decimal('NaN')
        except (InvalidOperation,TypeError,ValueError): value=Decimal('NaN')
        values[key]=value
        if not value.is_finite() or value<0 or (key=='loss' and value>1):
            reasons.append('invalid_'+label);continue
        if unit is not None and metric.get('unit')!=unit: reasons.append('invalid_'+label+'_unit')
        if key=='loss' and value>0: reasons.append('positive_loss')
        if key=='download_speed' and value==0: reasons.append('zero_speed')
        if key in ('sent','received') and value!=value.to_integral_value(): reasons.append('invalid_packet_evidence')
    sent,received=values['sent'],values['received']
    if sent is not None and received is not None and sent.is_finite() and received.is_finite():
        if sent<=0 or received!=sent: reasons.append('invalid_packet_evidence')
    for key,limit in [('measurement_time',POLICY['measurement_max_seconds']),('fetched_at',POLICY['fetch_max_seconds'])]:
        raw=p.get(key);seconds=age(raw,now)
        if seconds is None:
            (warnings if key=='measurement_time' and raw is None else reasons).append('unknown_'+key if raw is None else 'invalid_'+key)
        elif seconds<0: reasons.append('future_'+key)
        elif seconds>limit: reasons.append('stale_'+key)
    if p.get('valid_until') is not None:
        remaining=age(p['valid_until'],now)
        if remaining is None: reasons.append('invalid_valid_until')
        elif remaining>0: reasons.append('expired_observation')
    viewpoint=p.get('probe_viewpoint')
    if not isinstance(viewpoint,str) or viewpoint.strip().lower() in ('','unknown','n/a','none','null','-'):
        warnings.append('unknown_probe_viewpoint')
    if source.get('state')!='fresh': reasons.append('source_not_fresh')
    preferred=p.get('upstream_preferred') is True
    if not preferred: warnings.append('not_upstream_preferred')
    return dict(eligible=preferred and not reasons,level='upstream-preferred/unverified' if preferred else 'candidate/unverified',
                reasons=sorted(set(reasons)),warnings=sorted(set(warnings)))


def observation_reasons(p, now, source):
    return observation_quality(p,now,source)['reasons']


def evaluate(records, now, sources):
    """No best-observation cherry picking; unknown is not a negative vote."""
    for record in records:
        reasons=set();warnings=set();preferred=False
        for p in record['provenance']:
            p['quality']=observation_quality(p,now,sources.get(p['source_id'],{}))
            reasons.update(p['quality']['reasons']);warnings.update(p['quality']['warnings'])
            preferred=preferred or p.get('upstream_preferred') is True
        if not record['provenance']: reasons.add('no_observations')
        if not preferred: reasons.add('not_upstream_preferred')
        record['quality']=dict(policy_version=POLICY['version'],eligible=not reasons,
            level='upstream-preferred/unverified' if preferred else 'candidate/unverified',
            reasons=sorted(reasons),warnings=sorted(warnings),authenticated_proxy_health='not tested')
    return records
