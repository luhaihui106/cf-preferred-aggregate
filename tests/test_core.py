import unittest
import aggregate as a

HEADER = 'IP 地址,已发送,已接收,丢包率,平均延迟,下载速度 (MB/s)\n'

class ParserTests(unittest.TestCase):
    def test_csv_preserves_rank_metrics_unknowns(self):
        rows = a.parse_csv(HEADER + '104.16.0.1,4,4,0.00,58.16,28.52\n104.16.0.2,4,3,0.25,60,20\n')
        self.assertEqual([r['rank'] for r in rows], [1, 2])
        self.assertEqual(rows[0]['metrics']['download_speed'], {'value':'28.52','unit':'MB/s'})
        self.assertEqual(rows[0]['metrics']['latency']['unit'], None)
        self.assertEqual(rows[0]['measurement_time'], None)
        self.assertIsNone(rows[0]['port'])
    def test_csv_rejects_wrong_schema(self):
        with self.assertRaises(ValueError): a.parse_csv('address,speed\n104.16.0.1,20\n')
    def test_ranges_validate_family_and_public_edge(self):
        nets = a.parse_ranges('104.16.0.0/13\n', 4)
        self.assertEqual(a.valid_address('104.16.0.1',4,nets), '104.16.0.1')
        for ip in ['127.0.0.1','10.0.0.1','192.0.2.1','8.8.8.8','bad','2606:4700::1']:
            self.assertIsNone(a.valid_address(ip,4,nets))
        self.assertEqual(a.valid_address('2606:4700::0001',6,a.parse_ranges('2606:4700::/32',6)), '2606:4700::1')
        for text in ['', '0.0.0.0/0', '10.0.0.0/8','2606:4700::/32','104.16.0.1/13']:
            with self.assertRaises(ValueError): a.parse_ranges(text,4)

class MergeTests(unittest.TestCase):
    def test_round_robin_dedup_provenance_ports_conflicts(self):
        def row(ip, rank, carrier='general', port=None):
            return {'address':ip,'rank':rank,'port':port,'carrier_claim':carrier,'carrier_verified':False,'metrics':{}}
        records = a.merge([('one',[row('104.16.0.1',1,'cmcc'),row('104.16.0.2',2)]),
                           ('two',[row('104.16.0.1',1,'ct'),row('104.16.0.3',2),row('104.16.0.1',3,port=8443)])])
        self.assertEqual([(r['address'],r['port']) for r in records], [('104.16.0.1',None),('104.16.0.2',None),('104.16.0.3',None),('104.16.0.1',8443)])
        self.assertEqual(len(records[0]['provenance']),2)
        self.assertEqual(records[0]['carrier_claims'],['cmcc','ct'])
        self.assertTrue(records[0]['carrier_conflict'])
        self.assertEqual(records[0]['category'],'general')
        self.assertEqual(a.merge([]),[])
        self.assertEqual(records,a.merge([('one',[row('104.16.0.1',1,'cmcc'),row('104.16.0.2',2)]),('two',[row('104.16.0.1',1,'ct'),row('104.16.0.3',2),row('104.16.0.1',3,port=8443)])]))

if __name__ == '__main__': unittest.main()
