"""New recovery-v2 tests; claims about unrecovered old tests are not reused."""
import copy,json,unittest
from dataclasses import replace
from random import Random
from collections import Counter
from .integrity import make_queen,Seal,digest
from .racing import Program,INITIAL,UNIFORM,accept,candidates,Engine,race
from .study import episode,one_choice
from r4_r7 import search


def trained():
    q,w=make_queen(0)
    for i in range(24):
        raw,t,_=q.approximate_plan(q,[0,2],0,1,1,Random(i))
        r=q.execute_plan(w,[0,2],0,1,raw,raw,t,None,False,'recovery_dev')
        q.training_keys.append(r['label_key'])
    q.rebuild_monitor(q.training_keys,'development')
    return q,w


class IntegrityTests(unittest.TestCase):
    def test_live_counts_change_closes_query(self):
        q,w=trained();q.monitor.counts[(1,0)]=[100,100]
        self.assertEqual(q.current_reliability({'repeats':1,'margin':.1})['status'],'unknown')
    def test_live_total_change_closes_query(self):
        q,w=trained();q.monitor.total[0]+=1;self.assertFalse(q.monitor_valid())
    def test_live_support_change_closes_query(self):
        q,w=trained();q.monitor.support.pop();self.assertFalse(q.monitor_valid())
    def test_body_change_closes_query(self):
        q,w=trained();k=q.training_keys[0];r=q.ledger.records[k]
        q.ledger.records[k]=replace(r,body='{}');self.assertFalse(q.monitor_valid())
    def test_raw_intention_withdrawal_closes_query(self):
        q,w=trained();r=q.ledger.records[q.training_keys[0]]
        q.ledger.revoke(r.refs[0],'withdraw');self.assertFalse(q.monitor_valid());self.assertTrue(q.r_valid())
    def test_snapshot_cannot_change_live_probability(self):
        q,w=trained();t={'repeats':1,'margin':.1};a=q.current_reliability(t)
        a['snapshot']['cells'].clear();self.assertEqual(a['probability'],q.current_reliability(t)['probability'])
    def test_replaced_probability_method_not_called(self):
        q,w=trained();t={'repeats':1,'margin':.1};a=q.current_reliability(t)
        q.monitor.probability=lambda trace: .999
        self.assertEqual(a['probability'],q.current_reliability(t)['probability'])
    def test_unrelated_support_survives(self):
        q,w=trained();k=q.training_keys[0];before=q.ledger.records[k].body
        q.ledger.revoke(k,'withdraw');self.assertTrue(q.r_valid());self.assertEqual(q.ledger.records[k].body,before)
    def test_rebuild_uses_remaining_evidence(self):
        q,w=trained();q.ledger.revoke(q.training_keys[0],'withdraw')
        self.assertTrue(q.rebuild_monitor(q.training_keys,'remaining'));self.assertTrue(q.monitor_valid())
    def test_historical_review_not_dependent_on_truth(self):
        q,w=trained();k=q.monitor_ref;r=q.add('later_review',{'old':k},refs=(k,))
        q.ledger.revoke(k,'old invalid');self.assertNotIn(r,q.ledger.invalid)
    def test_meta_scale_content_gated(self):
        q,w=make_queen(0);q.meta_scale=3.
        with self.assertRaises(PermissionError):q.current_meta()
    def test_allocator_content_gated(self):
        q,w=make_queen(0);q.bind_allocator(INITIAL);q.allocator.ast='mean'
        with self.assertRaises(PermissionError):q.require_allocator()
    def test_meta_withdrawal_blocks_both_levels(self):
        q,w=make_queen(0);q.bind_allocator(INITIAL);q.search_program=search.Program(0);q.task_binding=q.search_program
        q.ledger.revoke(q.meta_ref,'withdraw')
        with self.assertRaises(PermissionError):q.require_allocator()
        p,h=search.make_problem(0)
        with self.assertRaises(PermissionError):q.execute_diagnosis(p,search.Body(p,h),search.Cost())
    def test_hidden_distribution_not_magic(self):
        q,w=trained();q.approximate_plan.donor=True
        self.assertTrue(q.monitor_valid()) # content integrity does not detect unobserved distribution shifts


class AllocationTests(unittest.TestCase):
    def test_grammar_no_io(self):
        with self.assertRaises(ValueError):Program('open')
    def test_budget_exact(self):
        calls=[];a,r=race(Program(INITIAL),[0,1],lambda a,j:calls.append((a,j)) or a,budget=8)
        self.assertEqual(len(calls),8)
    def test_one_initial_sample_each(self):
        _,r=race(Program(INITIAL),[0,1,2],lambda a,j:a,budget=6)
        self.assertEqual([x['arm'] for x in r['trace'][:3]],[0,1,2])
    def test_uncertainty_actual_input(self):
        p=Program(INITIAL)
        self.assertNotEqual(p((.2,.1,.1,0)),p((.2,.5,.1,0)))
    def test_candidates_distinct(self):
        c=candidates(INITIAL,0);self.assertEqual(len(c),8);self.assertEqual(len(set(map(str,c))),8)
    def test_strict_acceptance(self):
        self.assertFalse(accept([1,2,3],[1,2,3]));self.assertFalse(accept([.1,1,4],[1,2,3]))
    def test_current_parent_acceptance_not_frozen_parent(self):
        p=('-', 'mean', ('*',2,'uncert'));pool=candidates(p,0)
        e=Engine([0,'info'],[search.make_problem(i) for i in range(8)])
        _,r=one_choice(p,pool,e,1.,proposer=INITIAL)
        self.assertEqual(r['parent'],p);self.assertEqual(r['proposer'],INITIAL)
    def test_equal_inputs_deterministic(self):
        a=race(Program(INITIAL),[0,1],lambda a,j:(a+j%2)/3,budget=8)
        b=race(Program(INITIAL),[0,1],lambda a,j:(a+j%2)/3,budget=8)
        self.assertEqual(a,b)


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=episode(0)
    def test_same_object_ledger(self):self.assertTrue(self.r['same_queen'] and self.r['same_ledger'])
    def test_forecast_precedes_outcome(self):
        records=self.r['ledger']
        for row in self.r['rounds']:
            a=row['primary'];self.assertLess(a['prediction_key'],a['check_key'])
            self.assertEqual(records[a['prediction_key']]['kind'],'R22_forecast')
    def test_correctness_only_evaluator(self):
        for row in self.r['rounds']:
            for live in row['live']:
                self.assertEqual(live['observed']['identified'],live['evaluator_target'])
    def test_old_raw_data_retained(self):
        self.assertTrue(self.r['pressure']['old_body_unchanged'])
    def test_support_retraction_real(self):self.assertTrue(all(self.r['pressure'].values()))
    def test_plain_same_information(self):
        r=episode(0,'plain');r['method']='recursive'
        self.assertEqual(digest(r),digest(self.r))


if __name__=='__main__':unittest.main()
