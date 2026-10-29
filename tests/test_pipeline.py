import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import aggregate as a
from test_core import HEADER

NOW = '2026-10-29T12:00:00Z'

class PipelineTests(unittest.TestCase):
    def run_case(self, root, fail=(), now=NOW, ranges_fail=False):
        def fetch(url):
            if 'ips-v' in url:
                if ranges_fail: raise TimeoutError('range timeout')
                return '104.16.0.0/13\n' if url.endswith('v4') else '2606:4700::/32\n'
            if '/commits/main' in url:
                return json.dumps({'sha':'a'*40,'commit':{'committer':{'date':NOW}}})
            if url.endswith('/LICENSE'): return a.IPDB_LICENSE
            if any(url.endswith(f'ipv{f}.csv') for f in fail): raise TimeoutError('upstream timeout')
            if url.endswith('ipv4.csv'): return HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.1,4,4,0,10,20\n8.8.8.8,4,4,0,1,99\n'
            if url.endswith('ipv6.csv'): return HEADER+'2606:4700::1,4,4,0,20,10\n'
            if url.endswith('bestcfv4.txt'): return '104.16.0.1\n'
            if url.endswith('bestcfv6.txt'): return '2606:4700::1\n'
            raise AssertionError('unexpected URL: '+url)
        import pipeline
        with patch.object(pipeline,'SOURCES',[s for s in pipeline.SOURCES if s['provider_id']=='ipdb']):
            return a.generate(Path(root), now=now, fetch=fetch)

    def test_fresh_partial_full_failure_expiry_and_no_publish(self):
        with tempfile.TemporaryDirectory() as d:
            s = self.run_case(d)
            self.assertEqual(s['candidate_counts']['all-v4'],1)
            self.assertEqual(s['candidate_counts']['all-v6'],1)
            self.assertTrue(s['candidate_usable'])
            self.assertFalse(s['usable'])
            self.assertEqual(s['sources']['ipdb-v4']['input_rows'],3)
            self.assertEqual(s['sources']['ipdb-v4']['preferred_rows'],1)
            self.assertEqual(s['counts']['cmcc-v4'],0)
            first=(Path(d)/'records.json').read_bytes()
            self.assertEqual(self.run_case(d,fail=(4,))['sources']['ipdb-v4']['state'],'stale')
            s=self.run_case(d,fail=(4,6))
            self.assertFalse(s['published_dataset'])
            before=(Path(d)/'all-v4.txt').read_bytes()
            s=self.run_case(d,fail=(4,6),now='2026-10-31T12:00:00Z')
            self.assertFalse(s['usable'])
            self.assertEqual(s['state'],'expired')
            self.assertEqual(before,(Path(d)/'all-v4.txt').read_bytes())
            s=self.run_case(d,ranges_fail=True)
            self.assertFalse(s['published_dataset'])
            self.assertEqual(s['state'],'range_unavailable')
            self.assertTrue(first)
    def test_fetched_at_is_success_completion_not_attempt_start(self):
        with tempfile.TemporaryDirectory() as d:
            import pipeline
            with patch.object(pipeline,'utcnow',side_effect=['2026-10-29T12:00:00Z','2026-10-29T12:00:01Z','2026-10-29T12:00:02Z','2026-10-29T12:00:03Z','2026-10-29T12:00:04Z']):
                s=self.run_case(d,now=None)
            self.assertEqual(s['attempted_at'],'2026-10-29T12:00:00Z')
            self.assertEqual(s['sources']['ipdb-v4']['fetched_at'],'2026-10-29T12:00:02Z')
            self.assertEqual(s['sources']['ipdb-v6']['fetched_at'],'2026-10-29T12:00:03Z')

    def test_no_prior_outage_is_honest(self):
        with tempfile.TemporaryDirectory() as d:
            s=self.run_case(d,fail=(4,6))
            self.assertFalse(s['usable'])
            self.assertEqual(json.loads((Path(d)/'records.json').read_text())['records'],[])
            self.assertTrue((Path(d)/'status.json').exists())
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as x, tempfile.TemporaryDirectory() as y:
            self.run_case(x);self.run_case(y)
            self.assertEqual({p.name:p.read_bytes() for p in Path(x).iterdir()}, {p.name:p.read_bytes() for p in Path(y).iterdir()})
    def test_expired_partial_drops_failed_family(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_case(d)
            s=self.run_case(d,fail=(6,),now='2026-10-31T12:00:00Z')
            self.assertEqual(s['counts']['all-v6'],0)
            self.assertEqual(s['candidate_counts']['all-v4'],1)
            self.assertEqual(s['sources']['ipdb-v6']['state'],'expired')

class NetworkTests(unittest.TestCase):
    def test_stream_bounds_timeout_and_no_redirect(self):
        class Response(io.BytesIO):
            headers={}
            status=200
            def read1(self,n=-1):return self.read(n)
        calls=[]
        class Opener:
            def open(self,req,timeout):
                calls.append((req.full_url,timeout))
                return Response(b'abcde')
        with patch('urllib.request.build_opener',return_value=Opener()):
            with self.assertRaises(ValueError):a.fetch_text('https://example.com/a', max_bytes=4)
            self.assertEqual(a.fetch_text('https://example.com/a',max_bytes=5),'abcde')
        self.assertTrue(all(0 < t <= 10 for _,t in calls))
        with self.assertRaises(ValueError): a.fetch_text('http://example.com')
        with self.assertRaises(ValueError): a.fetch_text('https://u:p@example.com')
        with self.assertRaises(Exception):a.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')
    def test_timeout_is_bounded_and_retried(self):
        calls=[]
        class Opener:
            def open(self,req,timeout):calls.append(timeout);raise TimeoutError('timeout')
        with patch('urllib.request.build_opener',return_value=Opener()):
            with self.assertRaises(TimeoutError):a.fetch_text('https://example.com')
        self.assertEqual(len(calls),2)

if __name__=='__main__':unittest.main()
