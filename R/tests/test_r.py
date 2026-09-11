"""Development-only tests; confirmatory cohorts must not be imported as fixtures."""
import copy,json,unittest
from src.core import Queen,World,Port,PRIOR,QUERIES,score_program,choose,propose,NotLicensed
from src.study import emitter,episode,stress,interventions,history_tests


def setup():
    q=Queen();w=World((0,0,'less',3,[3,2,4,5]));q._emit=emitter(2);w.bias=[1,4]
    return q,w,Port(w)


class RTests(unittest.TestCase):
    def test_subclasses_original_queen(self):
        from library_m54.queen import Queen as Original
        self.assertTrue(issubclass(Queen,Original))

    def test_bootstrap_unknown_and_gate(self):
        q,w,p=setup();self.assertEqual(len(q.H),1764)
        self.assertFalse(q.r_valid());self.assertFalse(q.step(p,0,1)['executed'])

    def test_diagnosis_from_actual_receipts(self):
        q,w,p=setup();r=q.diagnose(p)
        self.assertEqual(r['identified'],[2,1,4,3]);self.assertTrue(q.r_valid())
        self.assertTrue(q.step(p,0,3)['executed']);self.assertEqual(w.positions[0],3)

    def test_hidden_labels_not_public(self):
        q,w,p=setup()
        self.assertFalse(hasattr(p,'parameters'));self.assertFalse(hasattr(p,'truth'))
        with self.assertRaises(ValueError):q.decode({'workers':[[1,2],[1,2]],'correct':True})

    def test_predictions_precede_own_receipt_and_result(self):
        q,w,p=setup();q.diagnose(p);r=q.step(p,0,3)
        self.assertLess(r['forecast'],r['intention']);self.assertLess(r['intention'],r['observation'])
        self.assertEqual(r['predicted_issued'],r['issued'])

    def test_own_change_detected_without_task_reward(self):
        q,w,p=setup();q.diagnose(p);q._emit=emitter(4)
        goal=(w.positions[0]+1)%7;r=q.step(p,0,goal)
        self.assertTrue(r['mismatch']);self.assertFalse(q.r_valid())
        self.assertEqual(q.diagnose(p)['identified'],[4,1,4,3])

    def test_world_change_not_own_change(self):
        q,w,p=setup();q.diagnose(p);w.parameters=(0,0,'less',3,[5,2,4,5])
        r=q.diagnose(p);self.assertEqual(r['identified'],[2,1,4,5])

    def test_worker_change_not_own_change(self):
        q,w,p=setup();q.diagnose(p);w.bias=[2,6]
        self.assertEqual(q.diagnose(p)['identified'],[2,2,6,3])

    def test_action_binding_has_evidence(self):
        q,w,p=setup();r=q.diagnose(p)
        self.assertIn('plan',r['task_source']);self.assertTrue(r['actual_plan_binding_changed'])
        self.assertTrue(q.ledger.records[q.permission].deps)

    def test_tampered_plan_binding_closes_gate(self):
        q,w,p=setup();q.diagnose(p);q.action_program=lambda p,g:0
        self.assertFalse(q.r_valid())

    def test_tampered_self_options_close_gate(self):
        q,w,p=setup();q.diagnose(p);q.self_options=(3,)
        self.assertFalse(q.r_valid())

    def test_unknown_self_has_only_common_actions(self):
        self.assertEqual(propose(tuple(range(1,7)),3,2,2),0)
        self.assertIsNone(propose(tuple(range(1,7)),3,2,3))

    def test_matched_intervention_recovery(self):
        q,w,p=setup();q.diagnose(p);a=interventions(q,w,0)['counts']
        self.assertEqual(a['full_correct'],28);self.assertEqual(a['restored_correct'],28)
        self.assertEqual(a['composite_correct'],28);self.assertLess(a['swapped_correct'],14)
        self.assertLess(a['removed_correct'],14)

    def test_symmetry_not_guessed(self):
        q,w,p=setup();q.diagnose(p);q.step(p,0,3);r=history_tests(q,w,0)
        self.assertEqual(r['symmetric'],[.5,.5]);self.assertTrue(r['equivariant'])

    def test_identity_metadata_rejected(self):
        q,w,p=setup();q.diagnose(p);e=q.step(p,0,3)
        with self.assertRaises(ValueError):q.attribute(e['intention'],{'paths':[],'author':'Queen'})

    def test_evidence_withdrawal_not_global_amnesia(self):
        q,w,p=setup();q.diagnose(p)
        k=next(r.seq for r in reversed(q.ledger.records) if r.kind=='R_calibration')
        s=q.self_permission;g=q.scope;q.ledger.revoke(k,'untrusted marker')
        self.assertFalse(q.r_valid());self.assertNotIn(s,q.ledger.invalid);self.assertNotIn(g,q.ledger.invalid)
        self.assertEqual(q.diagnose(p)['status'],'adopted')

    def test_old_wrong_claim_can_be_reviewed(self):
        q,w,p=setup();q.diagnose(p);q._emit=emitter(5);q.step(p,0,(w.positions[0]+1)%7)
        q.diagnose(p);r=q.retrospective();self.assertIsNotNone(r['old'])
        self.assertEqual(r['current_self_options'],[5])

    def test_nonlinear_known_counterexample_not_relicensed(self):
        s=stress()['nonlinear_self'];self.assertTrue(s['initially_licensed'])
        self.assertTrue(s['future']['mismatch']);self.assertTrue(s['revoked_after_counterexample'])
        self.assertFalse(s['relicensed_by_inadequate_recheck'])

    def test_uncertain_self_and_correct_control_distinct(self):
        s=stress()['self_uncertain_control_certain'];self.assertEqual(len(s['own_multiplier_options']),6)
        self.assertEqual(len(s['action_options']),1)

    def test_score_language_rejects_arbitrary_code(self):
        with self.assertRaises(ValueError):score_program('__import__')
        with self.assertRaises(ValueError):score_program(('exec','index','balance'))

    def test_meta_updates_actual_query_and_candidate_order_function(self):
        q,w,p=setup();q.diagnose(p);old=q.policy;r=q.evolve(0)
        self.assertTrue(r['accepted']);self.assertIsNot(q.policy,old)
        r2=q.evolve(1);self.assertEqual(r2['proposer_source'],r['new_source'])
        self.assertTrue(r2['uses_parent_policy_to_order_candidates'])

    def test_frozen_proposer_counterfactual_budget(self):
        q,w,p=setup();q.diagnose(p);q.evolve(0);a=copy.deepcopy(q);b=copy.deepcopy(q)
        x=a.evolve(42);y=b.evolve(42,True)
        self.assertEqual(x['proposed_asts'],y['proposed_asts']);self.assertEqual(x['fully_evaluated'],y['fully_evaluated'])
        self.assertNotEqual(x['proposer_source'],y['proposer_source'])

    def test_persistent_lineage_and_read_only_baseline(self):
        e=episode(0,'evolve');self.assertEqual(e['counts']['same_queen'],1)
        self.assertEqual(len(e['meta']),3);self.assertGreater(e['counts']['model_changes'],1)

    def test_same_information_plain_log(self):
        a=episode(1,'evolve');b=episode(1,'plain')
        self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['actual_cost'],b['actual_cost'])

if __name__=='__main__':unittest.main()
