"""连续路径的执行、匿名性、门禁和预算回归；不将单元测试当独立自然样本。"""
import json
import unittest
from dataclasses import FrozenInstanceError
from random import Random
from library_m12.core import compile_judge,Decision,PROGRAMS
from .core import Queen,Book,Budget,BudgetExceeded,NotLicensed,probe_packet,digest
from .world import World
from .identity import project,posterior,build_case,revisit
from .study import one_episode,scheme,run_batch,expected_patch
from .pressure import setup,run


class ContinuityTests(unittest.TestCase):
    def test_three_real_cycles_same_instance(self):
        r=one_episode(0,'library',True)
        self.assertTrue(r['counts']['same_queen'])
        self.assertGreaterEqual(len(r['substantive_cycles']),3)
        self.assertTrue(r['counts']['history_preserved'])
        self.assertEqual(r['counts'].get('wrong_patch_sets',0),0)

    def test_ledger_shared_through_all_stages(self):
        q,w=setup();old=q.book.ledger;history=q.history
        w.change('self',q,Random(1));q.act('apple',2,1);q.review(1)
        self.assertIs(q.book.ledger,old);self.assertIs(q.history,history)
        kinds={r.kind for r in q.book.ledger.records}
        self.assertTrue({'self_probe','calibration','review','permission'}<=kinds)

    def test_faults_do_not_reset_model(self):
        q,w=setup();before=q.book.export();previous=q.hypotheses
        w.change('environment',q,Random(2));q.act('apple',4,1);r=q.review(1,True)
        self.assertEqual(r['prior_hypotheses'],previous)
        self.assertIn('environment',r['reopened_coordinates'])
        self.assertEqual(q.book.export()[:len(before)],before)

    def test_judge_repair_is_actual_binding(self):
        q,w=setup();w.change('self',q,Random(3));old=q._judge
        q.act('apple',2,1);r=q.review(1,True)
        self.assertIn('queen_judge',r['patches']);self.assertIsNot(q._judge,old)
        self.assertTrue(r['actual_judge_binding_changed'])

    def test_worker_fault_does_not_replace_healthy_judge(self):
        q,w=setup();old=q._judge;w.change('worker',q,Random(1))
        q.act('apple',4,1);r=q.review(1,True)
        self.assertIs(q._judge,old);self.assertNotIn('queen_judge',r['patches'])

    def test_healthy_does_not_recalibrate(self):
        q,w=setup();old=(q._judge,w.workers[0].decoder,w.workers[1].decoder)
        r=q.review(1,True)
        self.assertEqual(r['patches'],[])
        self.assertEqual(old,(q._judge,w.workers[0].decoder,w.workers[1].decoder))

    def test_fingerprints_not_diagnostic_answers(self):
        q,w=setup();q._judge=compile_judge((1,1,2));q._judge.fingerprint='healthy'
        q.act('apple',3,1);r=q.review(1,True)
        self.assertIn('queen_judge',r['patches'])

    def test_hidden_schedule_is_method_independent(self):
        r=run_batch([0],trace_first=False)
        self.assertTrue(all(e['events_evaluator_only']==r['episodes'][0]['events_evaluator_only']
                            for e in r['episodes']))

    def test_plain_log_equals_primary(self):
        a,b=[one_episode(1,m,False) for m in ('library','plain')]
        self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['budget_cost'],b['budget_cost'])
        self.assertEqual([r['future'] for r in a['rows']],[r['future'] for r in b['rows']])

    def test_masked_can_probe_but_cannot_restore_missing_identity(self):
        r=one_episode(0,'masked',False)
        self.assertEqual(r['counts']['post_review_correct'],r['counts']['post_review_tasks'])
        self.assertEqual(r['counts'].get('identity_correct',0),0)
        self.assertEqual(r['counts']['false_certainty'],0)

    def test_budget_requests_counted(self):
        r=one_episode(0,'library',False)
        for row in r['rows']:
            if row['audit']:
                b=row['audit']['budget']
                for k in ('reads','probes','comparisons'):self.assertLessEqual(b[k],b['max_'+k])


class EvidenceTests(unittest.TestCase):
    def test_no_future_read(self):
        b=Book();k=b.append('x','worker',{'v':1})
        with self.assertRaises(ValueError):b.read(k,Budget(),-1)

    def test_payload_copy(self):
        b=Book();obj={'v':[1]};k=b.append('x','worker',obj);obj['v'].append(2)
        out=b.read(k,Budget());out['v'].append(3)
        self.assertEqual(b.read(k,Budget()),{'v':[1]})

    def test_record_is_frozen(self):
        b=Book();k=b.append('x','worker',{})
        with self.assertRaises(FrozenInstanceError):b.ledger.records[k].source='Queen'

    def test_reference_survives_invalid_assumption(self):
        b=Book();a=b.append('assumption','queen',{});c=b.append('claim','queen',{},deps=(a,))
        r=b.append('review','queen',{},refs=(c,));b.revoke(a,'contradiction')
        self.assertIn(c,b.ledger.invalid);self.assertNotIn(r,b.ledger.invalid)

    def test_all_budgets_enforced(self):
        for k in ('reads','probes','comparisons'):
            b=Budget();setattr(b,'max_'+k,0)
            with self.assertRaises(BudgetExceeded):b.spend(k)

    def test_second_world_cannot_attach(self):
        q,w=setup()
        with self.assertRaises(ValueError):q.attach(World().port())

    def test_no_correct_model_argument_in_review(self):
        import inspect
        self.assertEqual(list(inspect.signature(Queen.review).parameters),['self','tick','force'])


class AttributionTests(unittest.TestCase):
    def test_same_actions_remain_ambiguous(self):
        w={'commands':[1],'deltas':[1]}
        self.assertEqual(posterior(w,[w,w])['probabilities'],[.5,.5])

    def test_graph_and_ids_stripped(self):
        a={'commands':[1],'id':9,'author':'Queen','refs':[1,2],'fingerprint':'good'}
        self.assertEqual(project(a),{'commands':[1]})

    def test_nested_identity_payload_rejected(self):
        with self.assertRaises(ValueError):project({'commands':[{'author':'Queen'}]})

    def test_permutation_equivariance(self):
        w={'commands':[1]};a=[{'commands':[0]},{'commands':[1]}]
        self.assertEqual(posterior(w,a)['probabilities'],list(reversed(posterior(w,a[::-1])['probabilities'])))

    def test_state_merge_cannot_disambiguate(self):
        w={'commands':[1],'endpoint':[2,3]}
        self.assertEqual(posterior(w,[{'endpoint':[2,3]}]*2)['status'],'ambiguous')

    def test_absent_observation_does_not_authorize(self):
        self.assertEqual(posterior({'commands':[1]},[{},{}])['probabilities'],[.5,.5])

    def test_conflicting_histories_rejected(self):
        self.assertEqual(posterior({'commands':[1]},[{'commands':[2]},{'commands':[3]}])['status'],'inconsistent')

    def test_changed_behavior_is_actually_different(self):
        r=one_episode(0,'library',False)
        changed=[v for v in r['identity'] if v['kind']=='changed']
        self.assertTrue(changed)
        for row in changed:
            v=row['other_execution'];self.assertNotEqual(v['self_actual_command'],v['other_executed_commands'][0])
            self.assertTrue(row['correct_as_scoped'])


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=run()

    def test_rejected_candidate_preserves_program(self):self.assertTrue(self.r['bad_candidate_rejected'])
    def test_real_late_counterexample_rolls_back(self):
        self.assertTrue(self.r['tentative_accepted'] and self.r['later_error_observed'] and self.r['automatic_rollback'])
    def test_every_task_entry_blocks(self):self.assertTrue(self.r['all_four_entries_blocked'])
    def test_reproof_restores_future(self):self.assertTrue(self.r['revalidated_future_restored'])
    def test_unsupported_environment_abstains(self):self.assertTrue(self.r['outside_gain_abstains'])
    def test_cross_object_change_abstains(self):self.assertTrue(self.r['cross_object_drift_abstains'])
    def test_nonlinear_sensor_abstains(self):self.assertTrue(self.r['nonlinear_sensor_abstains'])
    def test_finite_validation_is_not_omniscience(self):self.assertTrue(self.r['latent_false_confidence_before_counterexample'])


if __name__=='__main__':unittest.main()
