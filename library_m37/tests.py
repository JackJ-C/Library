import json
import unittest
from dataclasses import replace
from library_m33.world import World, Port
from library_m33.queen import HYPOTHESES
from .grounded import GroundedQueen


class GroundedTests(unittest.TestCase):
    def _suspended_failure(self):
        q,w=GroundedQueen(),World(9)
        q.review(Port(w),bootstrap=True)
        q._judge.sign=-1
        original=q.review
        q.review=lambda *args,**kwargs: None
        p=w.sense()[0]['positions'][0]
        frame=q.experience(Port(w),0,(p+2)%7)
        q.review=original
        return q,w,frame

    def test_reinspection_uses_actual_intention(self):
        q,w,f=self._suspended_failure()
        report=q.review(Port(w),f['slice'])
        self.assertEqual(report['status'],'adopted')
        self.assertTrue(report['diagnosis']['self'])
        replay=[json.loads(r.body) for r in q.ledger.records if r.kind=='cross_slice_reinspection'][-1]
        self.assertTrue(replay['self_intention_inspected'])
        self.assertGreater(replay['candidate_count_after_reinspection'],0)

    def test_corrupt_intention_changes_decision_with_same_cache_and_outcome(self):
        q,w,f=self._suspended_failure()
        unchanged_H=q.H
        key=f['intention_slice']; old=q.ledger.records[key]
        body=json.loads(old.body); body['action']=0
        q.ledger.records[key]=replace(old,body=json.dumps(body,sort_keys=True))
        self.assertEqual(q.H,unchanged_H)
        report=q.review(Port(w),f['slice'])
        self.assertEqual(report['status'],'model_inconsistent')
        self.assertFalse(q.valid())

    def test_masked_history_requires_real_new_self_probe(self):
        q,w,f=self._suspended_failure();q.method='masked'
        report=q.review(Port(w),f['slice'])
        self.assertIn(['self',1],[s['query'] for s in report['inference_steps']])
        self.assertTrue(report['diagnosis']['self'])

    def test_new_certificate_depends_on_replayed_intention(self):
        q,w,f=self._suspended_failure()
        q.review(Port(w),f['slice'])
        self.assertIn(f['intention_slice'],q.ledger.records[q.certificate].deps)
        self.assertIn(f['slice'],q.ledger.records[q.certificate].deps)

    def test_current_cache_is_not_a_hidden_identity_or_diagnosis_answer(self):
        q,w,f=self._suspended_failure()
        q.H=tuple(h for h in HYPOTHESES if h[0]==1) # Deliberately wrong cache.
        report=q.review(Port(w),f['slice'])
        self.assertEqual(report['status'],'adopted')
        self.assertTrue(report['diagnosis']['self'])

    def test_reinspection_remains_historical_not_identity_link(self):
        q,w,f=self._suspended_failure();q.review(Port(w),f['slice'])
        with self.assertRaises(ValueError):
            q.attribute({'observations':[], 'refs':[f['slice']]})


if __name__=='__main__':
    unittest.main()
