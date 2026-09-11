"""Mechanistic regressions and no-label-leak checks. Only development seeds."""
import unittest,json,copy,inspect
from random import Random
from dataclasses import replace
from .online import make_queen,MutablePlanner,direct_probability,choose_check
from .study import stream,STEPS
from .meta import EvaluationMonitor,guarded_successor
from r4_r7 import search


def trained():
    q,w=make_queen(0)
    for t in range(24):
        q.clock=t
        positions=[t%7,(t+1)%7]; obj=t%2; goal=(t+3)%7
        raw,trace,_=q.approximate_plan(q,positions,obj,goal,1,Random(t))
        result=q.execute_plan(w,positions,obj,goal,raw,raw,trace,.5,False,'development')
        q.training_keys.append(result['label_key'])
    q.rebuild_monitor(q.training_keys,'unit developmental evidence')
    return q,w


class EvidenceTests(unittest.TestCase):
    def test_intention_withdrawal_closes_model_not_unrelated_knowledge(self):
        q,w=trained();m=q.monitor_ref;label=q.training_keys[-1];intent=q.ledger.records[label].refs[0]
        before=q.ledger.records[m].body;own=q.self_permission;cal=q.calibration;scope=q.scope
        q.ledger.revoke(intent,'raw intention retracted')
        self.assertFalse(q.monitor_valid());self.assertEqual(q.current_reliability({'repeats':1,'margin':.3})['status'],'unknown')
        self.assertEqual(q.monitor_history(m)['body'],json.loads(before))
        for k in (own,cal,scope): self.assertNotIn(k,q.ledger.invalid)
        self.assertTrue(q.r_valid())

    def test_observation_withdrawal_closes_model(self):
        q,w=trained();label=q.training_keys[0];obs=q.ledger.records[label].refs[1]
        q.ledger.revoke(obs,'observation invalid');self.assertFalse(q.monitor_valid())

    def test_interpretation_has_both_semantic_dependencies(self):
        q,w=trained()
        for k in q.training_keys:
            r=q.ledger.records[k];self.assertTrue(set(r.refs)<=set(r.deps));self.assertIn(q.calibration,r.deps)

    def test_rebuild_excludes_retracted_pair(self):
        q,w=trained();k=q.training_keys[0];q.ledger.revoke(q.ledger.records[k].refs[0],'retracted')
        self.assertTrue(q.rebuild_monitor(q.training_keys,'remaining valid evidence'))
        self.assertNotIn(k,q.monitor.support);self.assertTrue(q.monitor_valid())

    def test_false_cached_correct_is_not_used(self):
        q,w=trained();old=q.monitor.export()
        for k in q.training_keys:
            r=q.ledger.records[k];q.ledger.records[k]=replace(r,body=json.dumps({'correct':False}))
        q.rebuild_monitor(q.training_keys,'raw evidence recheck')
        self.assertEqual(q.monitor.export(),old)

    def test_historical_reference_not_proof_dependency(self):
        q,w=trained();m=q.monitor_ref;k=q.training_keys[0]
        review=q.add('later_review',{'old_model_wrong':True},refs=(m,))
        q.ledger.revoke(k,'bad support');self.assertNotIn(review,q.ledger.invalid)

    def test_old_data_cannot_license_registered_new_planner(self):
        q,w=trained();old=q.monitor_ref;q.approximate_plan=MutablePlanner()
        self.assertEqual(q.current_reliability({'repeats':1,'margin':.3})['status'],'unknown')
        self.assertFalse(q.rebuild_monitor(q.training_keys,'old rows after binding change'))
        self.assertFalse(q.monitor_valid());self.assertFalse(q.monitor_history(old)['current'])

    def test_same_callable_hidden_change_not_magically_known(self):
        q,w=trained();p=q.approximate_plan;p.donor=True
        self.assertIs(q.approximate_plan,p);self.assertTrue(q.monitor_valid())
        # This explicitly preserves the limitation: detection needs subsequent evidence.

    def test_checked_action_does_not_label_unexecuted_raw_answer(self):
        q,w=trained();r=q.execute_plan(w,[0,2],0,1,2,1,{'repeats':1,'margin':.3},.5,True,'dev')
        self.assertIsNone(r['label_key'])

    def test_worker_conflict_not_mistaken_for_self_planning_error(self):
        q,w=trained();w.bias[1]=1
        r=q.execute_plan(w,[0,2],0,1,2,2,{'repeats':1,'margin':.3},.5,False,'dev')
        self.assertFalse(r['consistent']);self.assertIsNone(r['label_key']);self.assertFalse(q.monitor_valid())

    def test_registered_change_can_relearn_from_new_actual_evidence(self):
        q,w=trained();q.approximate_plan=MutablePlanner()
        q.current_reliability({'repeats':1,'margin':.3});fresh=[]
        for t in range(24):
            raw,trace,_=q.approximate_plan(q,[0,2],0,1,1,Random(t))
            r=q.execute_plan(w,[0,2],0,1,raw,raw,trace,None,False,'new process')
            fresh.append(r['label_key'])
        self.assertTrue(q.rebuild_monitor(fresh,'new observations'));self.assertTrue(q.monitor_valid())

    def test_invalid_metadata_not_an_introspection_answer(self):
        q,w=trained()
        with self.assertRaises(ValueError):q.current_reliability({'repeats':1,'margin':.3,'correct':True})


class OnlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=stream(0,'adaptive',True);cls.p=stream(0,'plain');cls.c=stream(0,'compiled');cls.f=stream(0,'frozen')
    def test_one_object_and_ledger(self):self.assertTrue(self.a['same_queen'] and self.a['same_ledger'])
    def test_exact_quota_without_future_inputs(self):
        for a in (self.a,self.p,self.c,self.f):
            for i in range(0,STEPS,32):self.assertEqual(sum(r['checked'] for r in a['rows'][i:i+32]),8)
    def test_future_reordering_cannot_change_first_decision(self):
        # The decision primitive accepts only the current forecast and current quota.
        self.assertEqual(list(inspect.signature(choose_check).parameters),['p','remaining','slots_left'])
    def test_plain_and_compiled_independent_naming_equal(self):
        for other in (self.p,self.c):
            self.assertEqual(self.a['counts'],other['counts']);self.assertEqual(self.a['rows'],other['rows'])
    def test_same_first_order_raw_answers_in_all_arms(self):
        for other in (self.p,self.c,self.f):
            self.assertEqual([(r['raw'],r['trace']) for r in self.a['rows']],[(r['raw'],r['trace']) for r in other['rows']])
    def test_old_and_new_models_exist_after_change(self):self.assertGreater(len(self.a['alarms']),0)
    def test_forecast_precedes_action_feedback(self):
        records=self.a['ledger']
        for r in self.a['rows']:
            self.assertLess(r['intention'],r['observation'])
            if r['model_before'] is not None:self.assertLess(r['model_before'],r['intention'])
            for k in ('correct','gold','true_author','planner_mode'):self.assertNotIn(k,json.loads(records[r['intention']]['body']))
    def test_uncertainty_survives_alarm(self):self.assertGreater(self.a['counts']['unknown'],0)
    def test_uniform_predictor_compilation(self):
        for repeats in (1,3):
            for margin in (0,.2,.3,.6,1.2,3):
                q,w=trained();self.assertEqual(direct_probability(q.monitor.export(),{'repeats':repeats,'margin':margin}),q.monitor.probability({'repeats':repeats,'margin':margin}))


class MetaTests(unittest.TestCase):
    def test_margin_uses_only_past_own_check_gaps(self):
        m=EvaluationMonitor();self.assertEqual(m.margin(),0)
        m.observe(.4,.1,0);self.assertAlmostEqual(m.margin(),.3)
    def test_retracted_meta_evidence_is_unknown(self):
        q,w=make_queen(0);m=EvaluationMonitor();k=q.add('meta_evidence',{})
        m.observe(.3,.2,k);q.ledger.revoke(k,'withdrawn')
        with self.assertRaises(PermissionError):m.margin(q)
    def test_parent_and_counter_same_candidate_set(self):
        q,w=make_queen(0);m=EvaluationMonitor();p,h=search.make_problem(0)
        data=[(p,h)]*8;pool=search.pool(0,0,24)
        a,ra=guarded_successor(q,0,search.Program(0),pool,data,search.Cost(),m)
        b,rb=guarded_successor(q,0,search.Program(0),pool,data,search.Cost(),m)
        self.assertEqual(a,b);self.assertEqual(ra,rb);self.assertEqual(len(ra['selected']),4)
    def test_future_readouts_absent_from_successor_arguments(self):
        self.assertNotIn('test_cases',inspect.signature(guarded_successor).parameters)
    def test_given_guard_can_reject_without_claiming_improvement(self):
        m=EvaluationMonitor();m.observe(1,-1,0);self.assertEqual(m.margin(),2)


if __name__=='__main__':unittest.main()
