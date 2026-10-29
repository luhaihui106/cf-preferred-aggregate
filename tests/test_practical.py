"""Practical aggregation policy: synthetic fixtures, not health probes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from aggregate import collect_ipdb, merge, parse_ip_list
from quality import evaluate
from test_core import HEADER

NOW='2026-10-29T12:00:00Z'

class PracticalTests(unittest.TestCase):
    def test_published_good_shortlist_unknown_context_admitted_unverified(self):
        rows=collect_ipdb(HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.2,4,4,0,10,40\n','104.16.0.1',4)
        for p in rows: p['fetched_at']=NOW
        records=merge([('ipdb',rows)])
        evaluate(records,NOW,{'ipdb':{'state':'fresh'}})
        self.assertTrue(records[0]['quality']['eligible'])
        self.assertEqual(records[0]['quality']['level'],'upstream-preferred/unverified')
        self.assertIn('unknown_measurement_time',records[0]['quality']['warnings'])
        self.assertIn('unknown_probe_viewpoint',records[0]['quality']['warnings'])
        self.assertIsNone(records[0]['provenance'][0]['measurement_time'])
        self.assertFalse(records[1]['quality']['eligible'])
        self.assertIn('not_upstream_preferred',records[1]['quality']['reasons'])

    def test_known_failures_expiry_and_conflicts_veto(self):
        base=collect_ipdb(HEADER+'104.16.0.1,4,4,0,10,20\n','104.16.0.1',4)[0]
        base['fetched_at']=NOW
        for key,value,reason in [('download_speed','0','zero_speed'),('loss','0.1','positive_loss'),
                                 ('loss','NaN','invalid_loss'),('latency','oops','invalid_latency')]:
            bad=copy.deepcopy(base);bad['metrics'][key]['value']=value
            records=merge([('good',[base]),('bad',[bad])])
            evaluate(records,NOW,{'good':{'state':'fresh'},'bad':{'state':'fresh'}})
            self.assertFalse(records[0]['quality']['eligible'])
            self.assertIn(reason,records[0]['quality']['reasons'])
        for field,value,reason in [('valid_until','2026-10-29T11:59:59Z','expired_observation'),
                                 ('measurement_time','2026-10-28T11:59:59Z','stale_measurement_time')]:
            bad=copy.deepcopy(base);bad[field]=value
            records=merge([('bad',[bad])]);evaluate(records,NOW,{'bad':{'state':'fresh'}})
            self.assertIn(reason,records[0]['quality']['reasons'])

    def test_shortlist_rank_order_and_raw_exclusion(self):
        rows=collect_ipdb(HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.2,4,4,0,10,40\n104.16.0.3,4,4,0,10,50\n',
                          '104.16.0.2\n104.16.0.1',4)
        self.assertEqual([p['address'] for p in rows],['104.16.0.2','104.16.0.1','104.16.0.3'])
        self.assertEqual([p['csv_rank'] for p in rows],[2,1,3])
        for p in rows:p['fetched_at']=NOW
        records=merge([('ipdb',rows)]);evaluate(records,NOW,{'ipdb':{'state':'fresh'}})
        self.assertEqual([r['address'] for r in records if r['quality']['eligible']],['104.16.0.2','104.16.0.1'])

    def test_plain_preferred_unknown_metrics_warn_not_fail(self):
        rows=parse_ip_list('104.16.0.1')
        rows[0]['fetched_at']=NOW
        records=merge([('api',rows)])
        evaluate(records,NOW,{'api':{'state':'fresh'}})
        self.assertTrue(records[0]['quality']['eligible'])
        self.assertIn('unknown_loss',records[0]['quality']['warnings'])
        self.assertIn('unknown_speed',records[0]['quality']['warnings'])
        self.assertEqual(records[0]['quality']['authenticated_proxy_health'],'not tested')
