import unittest
from aggregate import merge, parse_csv
from test_core import HEADER
import pipeline

NOW='2026-10-29T12:00:00Z'

class QualityTests(unittest.TestCase):
    def test_present_bad_ipv6_excluded_unknown_context_ipv4_warns(self):
        self.assertTrue(hasattr(pipeline, 'evaluate'), 'current publisher has no recommendation gate')
        evaluate=pipeline.evaluate
        rows=parse_csv(HEADER+'2606:4700::1,4,3,0.25,10,0\n104.16.0.1,4,4,0,10,20\n')
        for p in rows: p.update(upstream_preferred=True,fetched_at=NOW)
        records=merge([('ipdb',rows)])
        evaluate(records,NOW,{'ipdb':{'state':'fresh'}})
        self.assertFalse(records[0]['quality']['eligible'])
        self.assertTrue(records[1]['quality']['eligible'])
        self.assertIn('positive_loss',records[0]['quality']['reasons'])
        self.assertIn('zero_speed',records[0]['quality']['reasons'])
        self.assertIn('unknown_measurement_time',records[1]['quality']['warnings'])

    def good(self):
        p=parse_csv(HEADER+'104.16.0.1,4,4,0,10,20\n')[0]
        p.update(upstream_preferred=True,measurement_time=NOW,fetched_at=NOW,probe_viewpoint='upstream probe AS64500; network context declared')
        return p

    def test_metric_time_boundaries_and_all_observation_conflicts(self):
        import copy
        from quality import evaluate
        good=self.good()
        def check(p):
            r=merge([('one',[p])]);evaluate(r,NOW,{'one':{'state':'fresh'}});return r[0]['quality']
        self.assertTrue(check(good)['eligible'])
        for metric,value,reason in [('loss','0.1','positive_loss'),('loss','-1','invalid_loss'),('loss','2','invalid_loss'),
            ('loss','NaN','invalid_loss'),('download_speed','0','zero_speed'),('download_speed','-1','invalid_speed'),
            ('download_speed','inf','invalid_speed')]:
            p=copy.deepcopy(good);p['metrics'][metric]['value']=value
            self.assertIn(reason,check(p)['reasons'])
        for field,value,reason in [('measurement_time','2026-10-28T11:59:59Z','stale_measurement_time'),
            ('measurement_time','2026-10-29T12:00:01Z','future_measurement_time'),('measurement_time','2026-10-29T12:00:00','invalid_measurement_time'),
            ('fetched_at','2026-10-28T11:59:59Z','stale_fetched_at')]:
            p=copy.deepcopy(good);p[field]=value;self.assertIn(reason,check(p)['reasons'])
        p=copy.deepcopy(good);p['measurement_time']='2026-10-28T12:00:00Z'
        self.assertTrue(check(p)['eligible'])
        bad=copy.deepcopy(good);bad['metrics']['loss']['value']='0.25'
        r=merge([('one',[good]),('mirror',[bad])]);evaluate(r,NOW,{'one':{'state':'fresh'},'mirror':{'state':'fresh'}})
        self.assertFalse(r[0]['quality']['eligible'])
        self.assertEqual(len(r[0]['provenance']),2)
        self.assertTrue(r[0]['provenance'][0]['quality']['eligible'])

    def test_exact_decimal_and_packet_counts_do_not_round_into_health(self):
        import copy
        from quality import evaluate
        for key,value in [('loss','1e-999'),('loss','-1e-999'),('download_speed','-1e-999')]:
            p=copy.deepcopy(self.good());p['metrics'][key]['value']=value
            r=merge([('one',[p])]);evaluate(r,NOW,{'one':{'state':'fresh'}})
            self.assertFalse(r[0]['quality']['eligible'],(key,value))
        for sent,received in [('9007199254740993','9007199254740992'),(True,True)]:
            p=self.good();p['metrics']['sent']['value']=sent;p['metrics']['received']['value']=received
            r=merge([('one',[p])]);evaluate(r,NOW,{'one':{'state':'fresh'}})
            self.assertTrue(any(x.startswith('invalid_') for x in r[0]['quality']['reasons']))

    def test_descriptive_summary_uses_exact_metrics_too(self):
        rows=parse_csv(HEADER+'104.16.0.1,4,4,1e-999,10,1e-999\n')
        q=pipeline.summarize_quality(rows)
        self.assertEqual(q['nonzero_loss_rows'],1)
        self.assertEqual(q['zero_download_rows'],0)

    def test_loss_sample_evidence_and_placeholder_probe_rejected(self):
        from quality import evaluate
        p=self.good();p['metrics']['sent']['value']='0';p['probe_viewpoint']='unknown'
        r=merge([('one',[p])]);evaluate(r,NOW,{'one':{'state':'fresh'}})
        self.assertIn('invalid_packet_evidence',r[0]['quality']['reasons'])
        self.assertIn('unknown_probe_viewpoint',r[0]['quality']['warnings'])

class PublicationTests(unittest.TestCase):
    def test_positive_evidence_publish_then_outage_clears_without_padding(self):
        import tempfile,json
        from pathlib import Path
        from quality import POLICY
        from pipeline import publish
        p=QualityTests().good()
        p['measurement_time']='2026-10-29T11:00:00Z'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            status=dict(state='fresh',sources={'one':{'state':'fresh'}},attempted_at=NOW,
                dataset_valid_until='2026-10-30T12:00:00Z',usable=True,
                cloudflare_ranges={'networks':{'4':['104.16.0.0/13'],'6':['2606:4700::/32']}})
            s=publish(root,status,merge([('one',[p])]),NOW,True)
            self.assertEqual(s['counts']['all-v4'],1)
            self.assertEqual(s['recommendation_state'],'upstream-preferred')
            self.assertEqual(s['recommendation_valid_until'],'2026-10-30T11:00:00Z')
            self.assertEqual(json.loads((root/'records.json').read_text())['valid_until'],s['recommendation_valid_until'])
            before=(root/'last-good-candidates.json').read_bytes()
            status.update(state='stale',sources={'one':{'state':'stale'}})
            s=publish(root,status,json.loads((root/'candidates.json').read_text())['records'],NOW,False)
            self.assertFalse(s['usable'])
            self.assertEqual((root/'all-v4.txt').read_text(),'')
            self.assertEqual(before,(root/'last-good-candidates.json').read_bytes())
            import audit
            audit.check_data(root)

    def test_failed_conflicting_source_cannot_disappear_to_promote_endpoint(self):
        import tempfile,copy
        from unittest.mock import patch
        from pathlib import Path
        import json,aggregate
        sources=[s for s in pipeline.SOURCES if s['id'] in ('cf-speed-dns-v4','cmliussss-cmcc')]
        current=NOW
        def parse(text,**kwargs):
            p=QualityTests().good();p['measurement_time']=current
            if text=='bad': p['metrics']['loss']['value']='0.25'
            return [p]
        def fetch(url):
            if url.endswith('ips-v4'): return '104.16.0.0/13'
            if url.endswith('ips-v6'): return '2606:4700::/32'
            if '/commits/' in url: raise TimeoutError('not used')
            if url.endswith('ipTop10.html'): return 'good'
            if current!=NOW: raise TimeoutError('failed conflicting source')
            return 'bad'
        with tempfile.TemporaryDirectory() as d, patch.object(pipeline,'SOURCES',sources), patch.object(aggregate,'parse_ip_list',side_effect=parse):
            s=pipeline.generate(d,now=current,fetch=fetch)
            self.assertEqual(s['counts']['all-v4'],0)
            current='2026-10-31T12:00:00Z'
            s=pipeline.generate(d,now=current,fetch=fetch)
            self.assertEqual(s['counts']['all-v4'],0,'expired failed bad observation must not disappear to promote good one')
            r=json.loads((Path(d)/'candidates.json').read_text())['records'][0]
            self.assertEqual(len(r['provenance']),2)
            self.assertIn('source_not_fresh',r['quality']['reasons'])

    def test_full_candidates_upstream_preferred_and_exact_hashes(self):
        import tempfile, json, hashlib
        from pathlib import Path
        from test_pipeline import PipelineTests
        with tempfile.TemporaryDirectory() as d:
            s=PipelineTests().run_case(d)
            root=Path(d)
            self.assertEqual(s['schema_version'],3)
            self.assertEqual(s['candidate_counts']['all-v4'],1)
            self.assertEqual(s['counts']['all-v4'],1)
            self.assertEqual((root/'all-v4.txt').read_text(),'104.16.0.1\n')
            self.assertEqual((root/'recommended-v6.txt').read_text(),'2606:4700::1\n')
            self.assertEqual(len(json.loads((root/'candidates.json').read_text())['records']),2)
            self.assertTrue(s['usable'])
            self.assertEqual(s['recommendation_state'],'upstream-preferred')
            for name,digest in s['file_sha256'].items():
                self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
            s=PipelineTests().run_case(d,fail=(4,6),now='2026-11-01T12:00:00Z')
            self.assertEqual(s['recommendation_state'],'expired')
            self.assertTrue((root/'candidates.json').exists())
            self.assertEqual((root/'all-v4.txt').read_text(),'')

    def test_full_csv_preserved_not_just_upstream_shortlist(self):
        from aggregate import collect_ipdb
        rows=collect_ipdb(HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.2,4,3,0.25,10,0\n','104.16.0.1',4)
        self.assertEqual(len(rows),2)
        self.assertEqual([r['rank'] for r in rows],[1,2])
        self.assertEqual(rows[0]['shortlist_rank'],1)
        self.assertIsNone(rows[1]['shortlist_rank'])

    def test_full_csv_conflicts_retained_and_veto_recommendation(self):
        from aggregate import collect_ipdb
        from quality import evaluate
        rows=collect_ipdb(HEADER+'104.16.0.1,4,4,0,10,20\n104.16.0.1,4,0,1,10,0\n','104.16.0.1',4)
        self.assertEqual(len(rows),2)
        r=merge([('one',rows)]);evaluate(r,NOW,{'one':{'state':'fresh'}})
        self.assertEqual(len(r[0]['provenance']),2)
        self.assertIn('positive_loss',r[0]['quality']['reasons'])

    def test_recommendations_cleared_on_range_failure(self):
        import tempfile,json
        from pathlib import Path
        from test_pipeline import PipelineTests
        with tempfile.TemporaryDirectory() as d:
            s=PipelineTests().run_case(d)
            (Path(d)/'all-v4.txt').write_text('104.16.0.1\n')
            s=PipelineTests().run_case(d,ranges_fail=True)
            self.assertFalse(s['usable'])
            self.assertEqual((Path(d)/'all-v4.txt').read_text(),'')
            self.assertTrue((Path(d)/'candidates.json').exists())

if __name__=='__main__': unittest.main()
