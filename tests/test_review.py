"""Synthetic regressions for independent review R1/R2/R3."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import aggregate
import audit
import pipeline
from test_core import HEADER
import test_pipeline as fixtures

def fetcher(narrow=False,fail=False,scoped=False):
    def fetch(url):
        if url.endswith('ips-v4'):return '104.20.0.0/14\n' if narrow else '104.16.0.0/13\n'
        if url.endswith('ips-v6'):return '2606:4700::/32\n'
        if fail:raise TimeoutError('synthetic outage')
        if '/commits/main' in url:return json.dumps({'sha':'a'*40,'commit':{'committer':{'date':fixtures.NOW}}})
        if url.endswith('/LICENSE'):return pipeline.IPDB_LICENSE
        if url.endswith('bestcfv4.txt'): return '104.16.0.1\n104.20.0.1\n'
        if url.endswith('bestcfv6.txt'): return '2606:4700::1\n'
        if 'ipTop10.html' in url or 'cf.090227.xyz/' in url: raise TimeoutError('synthetic unavailable extra feed')
        ips=['104.16.0.1','104.20.0.1'] if url.endswith('ipv4.csv') else ['2606:4700::1%eth0' if scoped else '2606:4700::1']
        return HEADER+''.join(ip+',4,4,0,10,20\n' for ip in ips)
    return fetch

class ReviewRegressions(unittest.TestCase):
    def test_scoped_ipv6_is_not_portable_address(self):
        nets=aggregate.parse_ranges('2606:4700::/32',6)
        self.assertIsNone(aggregate.valid_address('2606:4700::1%eth0',6,nets))
        with tempfile.TemporaryDirectory() as d:
            s=pipeline.generate(d,now=fixtures.NOW,fetch=fetcher(scoped=True))
            self.assertEqual(s['counts']['all-v6'],0)
            audit.check_data(Path(d))
    def test_full_outage_range_revocation_marks_retained_snapshot_unusable(self):
        with tempfile.TemporaryDirectory() as d:
            pipeline.generate(d,now=fixtures.NOW,fetch=fetcher())
            before=(Path(d)/'all-v4.txt').read_bytes()
            s=pipeline.generate(d,now='2026-10-29T13:00:00Z',fetch=fetcher(narrow=True,fail=True))
            self.assertFalse(s['usable'])
            self.assertEqual(s['state'],'range_changed')
            self.assertTrue(before)
            self.assertEqual((Path(d)/'all-v4.txt').read_bytes(),b'')
            audit.check_data(Path(d))
    def test_partial_stale_expires_during_fetch(self):
        with tempfile.TemporaryDirectory() as d:
            f=fixtures.PipelineTests();f.run_case(d)
            with patch.object(pipeline,'utcnow',side_effect=[
                '2026-10-30T11:59:59Z','2026-10-30T12:00:02Z','2026-10-30T12:00:03Z',
                '2026-10-30T12:00:04Z']):
                s=f.run_case(d,fail=(4,),now=None)
            self.assertTrue(s['candidate_usable'])
            self.assertTrue(s['usable'])  # Fresh IPv6 survives; expired IPv4 does not.
            self.assertEqual(s['sources']['ipdb-v4']['state'],'expired')
            self.assertEqual(s['counts']['all-v4'],0)
            self.assertGreater(s['dataset_valid_until'],s['dataset_generated_at'])
            audit.check_data(Path(d))

if __name__=='__main__':unittest.main()
