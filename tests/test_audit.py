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
    def test_failed_state_retained_dataset_is_auditable(self):
        with tempfile.TemporaryDirectory() as d:
            p=fixtures.PipelineTests();p.run_case(d)
            p.run_case(d,fail=(4,6),now='2026-10-31T12:00:00Z')
            audit.check_data(Path(d))

if __name__=='__main__':unittest.main()
