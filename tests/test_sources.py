"""Synthetic fixtures only: minimal published feeds and explicit IPDB shortlist."""
import json
import tempfile
import unittest
from pathlib import Path
import aggregate
import pipeline
from test_core import HEADER

class SourceTests(unittest.TestCase):
    def test_minimal_lists_preserve_order_not_markup(self):
        rows=aggregate.parse_ip_list('104.16.0.2,104.16.0.1\n', separator='comma')
        self.assertEqual([r['address'] for r in rows],['104.16.0.2','104.16.0.1'])
        self.assertIsNone(rows[0]['measurement_time'])
        self.assertEqual(rows[0]['metrics'],{})
        with self.assertRaises(ValueError): aggregate.parse_ip_list('<html>104.16.0.1</html>',separator='comma')
        with self.assertRaises(ValueError): aggregate.parse_ip_list('104.16.0.1,'*21,separator='comma',limit=20)
        rows=aggregate.parse_ip_list('104.16.0.1#CF 移动优选\n',claim='cmcc')
        self.assertEqual(rows[0]['carrier_claim'],'cmcc')
        self.assertFalse(rows[0]['carrier_verified'])
        self.assertEqual(rows[0]['upstream_label'],'CF 移动优选')
        with self.assertRaises(ValueError): aggregate.parse_ip_list('104.16.0.1:443')
        with self.assertRaises(ValueError): aggregate.parse_ip_list('104.16.0.1%eth0')
    def test_explicit_shortlist_is_not_arbitrary_top_or_loss_filter(self):
        csv=HEADER+'104.16.0.1,4,4,0,10,0\n104.16.0.2,4,3,0.25,20,0\n'
        rows=aggregate.select_ipdb(csv,'104.16.0.2\n',4)
        self.assertEqual(rows[0]['address'],'104.16.0.2')
        self.assertEqual(rows[0]['rank'],1)
        self.assertEqual(rows[0]['csv_rank'],2)
        self.assertEqual(rows[0]['metrics']['loss']['value'],'0.25')
        with self.assertRaises(ValueError): aggregate.select_ipdb(csv,'104.16.0.3\n',4)
        with self.assertRaises(ValueError): aggregate.select_ipdb(csv,'104.16.0.2\n104.16.0.2\n',4)
    def test_multisource_live_contract_with_synthetic_fetch(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            if url.endswith('ips-v4'): return '104.16.0.0/13\n'
            if url.endswith('ips-v6'): return '2606:4700::/32\n'
            if '/commits/main' in url: return json.dumps({'sha':'a'*40,'commit':{'committer':{'date':'2026-10-29T12:00:00Z'}}})
            if url.endswith('/LICENSE'): return pipeline.IPDB_LICENSE
            if url.endswith('ipv4.csv'): return HEADER+'104.16.0.1,4,4,0,10,1\n104.16.0.2,4,3,0.25,20,0\n'
            if url.endswith('ipv6.csv'): return HEADER+'2606:4700::1,4,4,0,20,0\n'
            if url.endswith('bestcfv4.txt'): return '104.16.0.1\n'
            if url.endswith('bestcfv6.txt'): return '2606:4700::1\n'
            if url.endswith('ipTop10.html'): return '104.16.0.1,104.16.0.3\n'
            if url.endswith('/cmcc'): return '104.16.0.1#CF 移动优选\n8.8.8.8#bad\n'
            if url.endswith('/cu'): return '104.16.0.4#CF 联通优选\n'
            if url.endswith('/ct'): return '104.16.0.4#CF 电信优选\n'
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as d:
            s=pipeline.generate(d,now='2026-10-29T12:00:00Z',fetch=fetch)
            self.assertEqual(s['state'],'fresh')
            self.assertEqual(s['provider_count'],3)
            self.assertEqual(s['fresh_provider_count'],3)
            self.assertEqual(s['adapter_count'],6)
            self.assertEqual(s['candidate_counts']['all-v4'],4)
            self.assertEqual(s['counts']['all-v4'],0)
            self.assertEqual(s['counts']['cmcc-v4'],0)
            self.assertEqual(s['sources']['ipdb-v4']['input_rows'],2)
            self.assertEqual(s['sources']['ipdb-v4']['preferred_rows'],1)
            self.assertEqual(s['sources']['ipdb-v4']['quality_summary']['nonzero_loss_rows'],1)
            self.assertEqual(s['sources']['ipdb-v6']['quality_summary']['zero_download_rows'],1)
            self.assertEqual(s['sources']['cf-speed-dns-v4']['quality_summary'],None)
            self.assertEqual(s['sources']['cmliussss-cmcc']['rejected_rows'],1)
            records=json.loads((Path(d)/'candidates.json').read_text())['records']
            common=next(r for r in records if r['address']=='104.16.0.1')
            self.assertEqual(len(common['provenance']),3)
            self.assertEqual({p['provider_id'] for p in common['provenance']},{'ipdb','cf-speed-dns','cmliussss'})
            self.assertTrue(next(r for r in records if r['address']=='104.16.0.4')['carrier_conflict'])
            self.assertFalse(any('wetest' in url or 'BestCFip' in url for url in calls))

    def test_quality_unknown_is_not_nonzero(self):
        rows=aggregate.parse_csv(HEADER+'104.16.0.1,4,4,,10,unknown\n104.16.0.2,4,3,nan,20,inf\n')
        q=pipeline.summarize_quality(rows)
        self.assertEqual(q['nonzero_loss_rows'],0)
        self.assertEqual(q['unknown_loss_rows'],2)
        self.assertEqual(q['zero_download_rows'],0)
        self.assertEqual(q['unknown_download_rows'],2)

    def test_review_conflicting_csv_duplicate_fails_closed(self):
        csv=HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.1,4,0,1,999,0\n'
        with self.assertRaises(ValueError): aggregate.select_ipdb(csv,'104.16.0.1\n',4)
        identical=HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.1,4,4,0,10,20\n'
        selected=aggregate.select_ipdb(identical,'104.16.0.1\n',4)
        self.assertEqual(selected[0]['csv_ranks'],[1,2])
        self.assertEqual(len(selected),1)

    def test_review_comma_feed_also_accepts_explicit_newlines(self):
        rows=aggregate.parse_ip_list('104.16.0.1\n104.16.0.2,\n104.16.0.3\n',separator='comma')
        self.assertEqual([r['rank'] for r in rows],[1,2,3])

    def test_review_partial_snapshot_full_outage_keeps_own_ttl(self):
        def fetch(url):
            if url.endswith('ips-v4'):return '104.16.0.0/13\n'
            if url.endswith('ips-v6'):return '2606:4700::/32\n'
            if url.endswith('ipTop10.html'):return '104.16.0.1\n'
            raise TimeoutError('synthetic missing sources')
        def outage(url):
            if 'ips-v' in url:return fetch(url)
            raise TimeoutError('synthetic full outage')
        with tempfile.TemporaryDirectory() as d:
            first=pipeline.generate(d,now='2026-10-29T12:00:00Z',fetch=fetch)
            original=json.loads((Path(d)/'candidates.json').read_text())['records']
            self.assertTrue(first['candidate_usable'])
            s=pipeline.generate(d,now='2026-10-29T13:00:00Z',fetch=outage)
            self.assertTrue(s['candidate_usable'])
            self.assertFalse(s['usable'])
            self.assertEqual(s['state'],'stale')
            self.assertEqual(s['dataset_valid_until'],first['dataset_valid_until'])
            self.assertEqual(s['contributing_provider_count'],1)
            self.assertEqual([r['address'] for r in json.loads((Path(d)/'candidates.json').read_text())['records']],[r['address'] for r in original])
            s=pipeline.generate(d,now='2026-10-30T13:00:00Z',fetch=outage)
            self.assertFalse(s['usable'])
            self.assertEqual(s['state'],'expired')

    def test_additional_provider_failure_isolated_stale_then_expired(self):
        from unittest.mock import patch
        sources=[s for s in pipeline.SOURCES if s['provider_id']!='ipdb']
        def fetch(url):
            if url.endswith('ips-v4'): return '104.16.0.0/13\n'
            if url.endswith('ips-v6'): return '2606:4700::/32\n'
            if url.endswith('ipTop10.html'): return '104.16.0.1\n'
            if url.endswith('/cmcc'): return '104.16.0.2#CF 移动优选\n'
            if url.endswith('/cu'): return '104.16.0.3#CF 联通优选\n'
            if url.endswith('/ct'): return '104.16.0.4#CF 电信优选\n'
            raise TimeoutError('synthetic IPDB license/API unavailable')
        with tempfile.TemporaryDirectory() as d:
            s=pipeline.generate(d,now='2026-10-29T12:00:00Z',fetch=fetch)
            self.assertEqual(s['fresh_provider_count'],2)
            self.assertEqual(s['state'],'partial')
            self.assertEqual(s['sources']['ipdb-v4']['state'],'error')
            def fail_cmcc(url):
                if url.endswith('/cmcc'): raise TimeoutError('synthetic outage')
                return fetch(url)
            s=pipeline.generate(d,now='2026-10-29T13:00:00Z',fetch=fail_cmcc)
            cm=s['sources']['cmliussss-cmcc']
            self.assertEqual(cm['state'],'stale')
            self.assertEqual(cm['fetched_at'],'2026-10-29T12:00:00Z')
            self.assertEqual(cm['input_rows'],1)
            s=pipeline.generate(d,now='2026-10-31T13:00:00Z',fetch=fail_cmcc)
            self.assertEqual(s['sources']['cmliussss-cmcc']['state'],'expired')
            self.assertEqual(s['candidate_counts']['all-v4'],3)
            def fail_all(url):
                if 'ips-v' in url:return fetch(url)
                raise TimeoutError('all unavailable')
            before=(Path(d)/'candidates-v4.txt').read_bytes()
            s=pipeline.generate(d,now='2026-11-02T13:00:00Z',fetch=fail_all)
            self.assertFalse(s['usable'])
            self.assertEqual(s['fresh_provider_count'],0)
            self.assertEqual(before,(Path(d)/'candidates-v4.txt').read_bytes())

if __name__=='__main__': unittest.main()
