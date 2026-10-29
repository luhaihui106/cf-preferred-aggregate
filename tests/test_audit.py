import copy
import json
import tempfile
import unittest
from pathlib import Path
import audit
import test_pipeline as fixtures

class AuditTests(unittest.TestCase):
    def test_secret_boundary_and_url_allowlist(self):
        audit.check_text('public','https://www.cloudflare.com/ips-v4')
        for text in ['vless://example','https://example.com/?token=x','https://unknown.example/a',
                     'xxxxxxxx-xxxx-4xxx-8xxx-xxxxxxxxxxxx','/root/operations','-----BEGIN PRIVATE KEY-----']:
            with self.assertRaises(ValueError,msg=text):audit.check_text('fixture',text)
    def test_output_counts_hashes_family_and_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures.PipelineTests().run_case(d)
            audit.check_data(Path(d))
            p=Path(d)/'all-v4.txt'; p.write_text('104.16.0.1\n104.16.0.1\n')
            with self.assertRaises(ValueError):audit.check_data(Path(d))
    def test_candidate_tamper_and_bad_recommendation_caught(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures.PipelineTests().run_case(d)
            p=Path(d)/'candidates-v4.txt';p.write_text('104.16.0.9\n')
            with self.assertRaises(ValueError): audit.check_data(Path(d))

    def test_quality_reason_tamper_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            fixtures.PipelineTests().run_case(d)
            root=Path(d);p=root/'candidates.json';obj=json.loads(p.read_text())
            obj['records'][0]['quality']['reasons']=['invented_reason']
            p.write_text(json.dumps(obj))
            s=json.loads((root/'status.json').read_text())
            from collections import Counter
            s['exclusion_reasons']=dict(Counter(reason for r in obj['records'] for reason in r['quality']['reasons']))
            s['file_sha256']['candidates.json']=hashlib.sha256(p.read_bytes()).hexdigest()
            (root/'status.json').write_text(json.dumps(s))
            with self.assertRaises(ValueError): audit.check_data(root)

    def test_supported_maximum_rows_fit_publication_budget(self):
        from unittest.mock import patch
        import pipeline
        def fetch(url):
            if url.endswith('ips-v4'): return '104.16.0.0/13'
            if url.endswith('ips-v6'): return '2606:4700::/32'
            if '/commits/main' in url: return json.dumps({'sha':'a'*40,'commit':{'committer':{'date':fixtures.NOW}}})
            if url.endswith('/LICENSE'): return pipeline.IPDB_LICENSE
            if url.endswith('bestcfv4.txt'): return '104.16.0.1'
            if url.endswith('bestcfv6.txt'): return '2606:4700::1'
            from test_core import HEADER
            import ipaddress
            base=ipaddress.ip_address('104.16.0.1' if url.endswith('ipv4.csv') else '2606:4700::1')
            return HEADER+''.join(str(base+i)+',4,4,0,10,20\n' for i in range(1000))
        with tempfile.TemporaryDirectory() as d:
            with patch.object(pipeline,'SOURCES',pipeline.SOURCES[:2]):
                pipeline.generate(d,now=fixtures.NOW,fetch=fetch)
            self.assertTrue(all(p.stat().st_size<=audit.file_limit('data/'+p.name) for p in Path(d).iterdir()))
            audit.check_data(Path(d))

    def test_failed_state_retained_dataset_is_auditable(self):
        with tempfile.TemporaryDirectory() as d:
            p=fixtures.PipelineTests();p.run_case(d)
            p.run_case(d,fail=(4,6),now='2026-10-31T12:00:00Z')
            audit.check_data(Path(d))

if __name__=='__main__':unittest.main()
