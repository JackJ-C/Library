"""新接线的回归；旧M37的冻结测试另行保留。"""
import unittest
from random import Random
from library_m37.core import NotLicensed,probe_packet
from library_m37.world import World
from library_m37.pressure import exercise_rollback
from .integration import Queen,EvidenceBook,project,posterior,install


def setup():
    w=World();q=Queen();q.attach(w.port());q.review(0,True);return q,w


class IntegrationTests(unittest.TestCase):
    def test_every_observed_support_revokes_permission(self):
        q,w=setup();roots=q.audit_history[-1]['proof_support']
        for index in range(len(roots)):
            q,w=setup();k=q.audit_history[-1]['proof_support'][index]
            q.book.revoke(k,'retracted evidence')
            self.assertFalse(q.valid())
            for call in (lambda:q.decide(probe_packet(0)),lambda:q.predict(probe_packet(0))):
                with self.assertRaises(NotLicensed):call()
            self.assertFalse(q.act('apple',2,1)['executed'])
            self.assertFalse(q.execute('teacup',2,1)['executed'])
            r=q.review(2,True);self.assertEqual(r['status'],'accepted')
            self.assertTrue(q.act('apple',4,3)['executed']);self.assertEqual(w.positions['apple'],4)

    def test_outcome_dependency_not_only_action(self):
        q,w=setup();q.act('apple',4,1);r=q.review(1,True)
        outcome=q.last_outcome
        self.assertIn(outcome,r['proof_support'])
        q.book.revoke(outcome,'outcome withdrawn');self.assertFalse(q.valid())

    def test_future_intention_ignores_evaluator_positions(self):
        q,w=setup();a=q.act('apple',3,1)
        k=q.book.append('intention_memory','queen',{'commands':[999],'endpoint':[999,999],'author':'bad'},(a['action_ref'],))
        self.assertEqual(q.book.ledger.records[k].payload() if hasattr(q.book.ledger.records[k],'payload') else
                         __import__('json').loads(q.book.ledger.records[k].body)['data'],{'commands':[a['action']]})

    def test_candidate_positions_never_used(self):
        a={'commands':[1],'endpoint':[0,0],'author':'x'}
        self.assertEqual(project(a),{'commands':[1]})
        self.assertEqual(posterior(a,[a,dict(a,commands=[2])])['probabilities'],[1,0])

    def test_identical_and_merge_uncertainty(self):
        self.assertEqual(posterior({'commands':[1]},[{'commands':[1]}]*2)['probabilities'],[.5,.5])
        self.assertEqual(posterior({'commands':[1]},[{'endpoint':[2,3]}]*2)['probabilities'],[.5,.5])

    def test_reference_to_wrong_history_survives(self):
        q,w=setup();k=q.audit_history[-1]['proof_support'][0]
        r=q.book.append('review','queen',{'old_evidence_wrong':True},refs=(k,))
        q.book.revoke(k,'withdrawn');self.assertNotIn(r,q.book.ledger.invalid)
        self.assertFalse(q.valid())

    def test_continuous_small_lifetime(self):
        study=install();e=study.one_episode(0,'library',True)
        self.assertTrue(e['counts']['same_queen']);self.assertTrue(e['counts']['history_preserved'])
        self.assertGreaterEqual(len(e['substantive_cycles'])-1,3)
        self.assertEqual(e['counts'].get('wrong_patch_sets',0),0)
        self.assertTrue(all(e['post_episode_pressure'].values()))

    def test_actual_rollback_same_object(self):
        q,w=setup();self.assertTrue(all(exercise_rollback(q,w).values()))

    def test_plain_information_equivalence(self):
        s=install();a=s.one_episode(1,'library');b=s.one_episode(1,'plain')
        self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['budget_cost'],b['budget_cost'])

    def test_anonymized_packet_has_no_graph(self):
        a={'commands':[2],'refs':[1],'id':1,'fingerprint':'a','author':'Queen'}
        self.assertEqual(project(a),project(dict(a,refs=[7],id=9,author='other')))

    def test_invalid_candidate_vector(self):
        with self.assertRaises(ValueError):project({'commands':[{'id':1}]})

    def test_supports_retained_across_lifetimes(self):
        q,w=setup();b=q.book;old=q.book.export()
        w.change('self',q,Random(3));q.act('apple',2,1);q.review(1,True)
        self.assertIs(q.book,b);self.assertEqual(q.book.export()[:len(old)],old)


if __name__=='__main__':unittest.main()
