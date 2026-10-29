"""Source-claimed carrier exports are not verified carrier measurements."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from aggregate import merge, parse_ip_list
from pipeline import publish
import audit

NOW='2026-10-29T12:00:00Z'

class LightweightTests(unittest.TestCase):
    def rows(self, text, claim='general'):
        rows=parse_ip_list(text,claim=claim)
        for p in rows:
            p.update(fetched_at=NOW,provider_id='fixture',origin='https://example.com')
        return rows

    def publish(self, root, groups):
        status=dict(sources={sid:dict(state='fresh') for sid,_ in groups},state='fresh',
            attempted_at=NOW,dataset_valid_until='2026-10-30T12:00:00Z',
            cloudflare_ranges={'networks':{'4':['104.16.0.0/13'],'6':['2606:4700::/32']}})
        return publish(root,status,merge(groups),NOW,True)

    def test_claimed_groups_conflicts_attribution_and_general(self):
        groups=[('unlabelled',self.rows('104.16.0.1\n104.16.0.2')),
                ('mobile',self.rows('104.16.0.2#上游移动\n104.16.0.3','cmcc')),
                ('telecom',self.rows('104.16.0.2#上游电信','ct'))]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s=self.publish(root,groups)
            self.assertEqual(s['counts']['all-v4'],3)
            self.assertEqual((root/'general-v4.txt').read_text(),'104.16.0.1\n')
            self.assertEqual((root/'cmcc-v4.txt').read_text(),'104.16.0.2\n104.16.0.3\n')
            self.assertEqual((root/'ct-v4.txt').read_text(),'104.16.0.2\n')
            records=json.loads((root/'records.json').read_text())['records']
            common=next(r for r in records if r['address']=='104.16.0.2')
            self.assertTrue(common['carrier_conflict'])
            self.assertEqual(common['carrier_claim_sources'],{'cmcc':['mobile'],'ct':['telecom']})
            self.assertEqual(common['carrier_grouping'],'source-claimed/unverified')
            self.assertFalse(common['carrier_verified'])
            self.assertTrue(all(not p['carrier_verified'] for p in common['provenance']))
            self.assertEqual(common['category'],'general')  # compatibility; not a verified classification
            self.assertEqual(s['carrier_export_policy']['label'],'上游标注，未独立验证')
            audit.check_data(root)

    def test_any_bad_metric_vetoes_every_recommended_export(self):
        for metric,value,unit in [('loss','0.01','ratio'),('download_speed','0','MB/s'),
                                  ('download_speed','failed','MB/s')]:
            with self.subTest(metric=metric,value=value),tempfile.TemporaryDirectory() as d:
                bad=self.rows('104.16.0.2','ct')
                bad[0]['metrics']={metric:{'value':value,'unit':unit}}
                groups=[('general',self.rows('104.16.0.2')),('cmcc',self.rows('104.16.0.2','cmcc')),('bad',bad)]
                root=Path(d);s=self.publish(root,groups)
                self.assertTrue(all(n==0 for n in s['counts'].values()))
                self.assertEqual((root/'candidates-v4.txt').read_text(),'104.16.0.2\n')
                audit.check_data(root)

    def test_no_shuffle_or_fixed_five_truncation(self):
        ips=[f'104.16.0.{i}' for i in range(1,9)]
        groups=[('mobile',self.rows('\n'.join(ips),'cmcc')),
                ('general',self.rows('104.16.1.1\n104.16.1.2'))]
        expected=[ips[0],'104.16.1.1',ips[1],'104.16.1.2']+ips[2:]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.publish(root,groups)
            self.assertEqual((root/'all-v4.txt').read_text().splitlines(),expected)
            self.assertEqual((root/'cmcc-v4.txt').read_text().splitlines(),ips)
            self.assertEqual((root/'general-v4.txt').read_text().splitlines(),['104.16.1.1','104.16.1.2'])
            first=(root/'all-v4.txt').read_bytes()
            self.publish(root,copy.deepcopy(groups))
            self.assertEqual(first,(root/'all-v4.txt').read_bytes())
            audit.check_data(root)

    def test_resealed_carrier_metadata_tampering_rejected(self):
        import hashlib
        for target in ('record','observation','policy'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as d:
                root=Path(d);self.publish(root,[('mobile',self.rows('104.16.0.1','cmcc'))])
                if target=='policy':
                    status=json.loads((root/'status.json').read_text())
                    status['carrier_export_policy']['carrier_verified']=True
                    (root/'status.json').write_text(json.dumps(status))
                else:
                    for name in ('records.json','candidates.json'):
                        obj=json.loads((root/name).read_text())
                        record=obj['records'][0]
                        (record if target=='record' else record['provenance'][0])['carrier_verified']=True
                        (root/name).write_text(json.dumps(obj))
                    status=json.loads((root/'status.json').read_text())
                    for name in ('records.json','candidates.json'):
                        status['file_sha256'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
                    (root/'status.json').write_text(json.dumps(status))
                with self.assertRaises(ValueError):audit.check_data(root)

    def test_audit_rejects_forged_claim_sources_and_verification(self):
        for field,value in [('carrier_claim_sources',{'cmcc':['invented']}),('carrier_verified',True)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
                root=Path(d);self.publish(root,[('mobile',self.rows('104.16.0.1','cmcc'))])
                obj=json.loads((root/'records.json').read_text());obj['records'][0][field]=value
                (root/'records.json').write_text(json.dumps(obj))
                with self.assertRaises(ValueError):audit.check_data(root)
