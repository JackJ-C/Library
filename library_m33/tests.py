"""Tests use only development seeds. Validation seeds are consumed only after freeze."""
import copy
import json
import unittest
from .world import World, Port, Judge, MOD
from .queen import Queen, HYPOTHESES, Budget, compatible
from .study import timeline, anonymous_packet, pressure_cases


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.row = timeline(0, 'library')

    def test_same_instance_at_least_three_cycles(self):
        self.assertTrue(self.row['trace']['instance_preserved'])
        self.assertGreaterEqual(self.row['counts']['repair_cycles'], 3)
        self.assertEqual(self.row['counts']['state_retained'], 1)

    def test_actual_judge_binding_changes_only_for_self(self):
        for a in self.row['trace']['audits']:
            if a['review']['status'] in ('adopted', 'confirmed'):
                self.assertEqual(a['actual_binding_replaced'], a['expected_diagnosis']['self'])

    def test_future_actions_and_healthy_components(self):
        c = self.row['counts']
        self.assertEqual(c['future_correct'], c['future_checks'])
        self.assertEqual(c['healthy_component_mispatch'], 0)

    def test_intentions_exist_before_feedback(self):
        ledger = self.row['trace']['ledger']
        for r in ledger:
            if r['kind'] == 'experience':
                f = json.loads(r['body'])
                i = f['intention_slice']
                self.assertLess(i, r['seq'])
                intention = json.loads(ledger[i]['body'])
                self.assertEqual(intention['prediction'], f['prediction'])
                self.assertEqual(intention['action'], f['action'])

    def test_all_references_backward_and_dependencies_valid(self):
        ledger = self.row['trace']['ledger']
        for r in ledger:
            for key in r['refs'] + r['deps']:
                self.assertLess(key, r['seq'])
        self.assertTrue(any(r['kind']=='review' and r['refs'] for r in ledger))

    def test_worker_views_and_relations_are_in_every_slice(self):
        for r in self.row['trace']['ledger']:
            if r['kind']=='experience':
                f=json.loads(r['body'])
                for view in f['before']+f['after']:
                    a,b=view['positions']
                    self.assertEqual(view['relations']['same_place'], a==b)
                    self.assertEqual(view['relations']['apple_to_cup_clockwise'], (b-a)%MOD)

    def test_certificate_depends_on_used_current_experience(self):
        records=self.row['trace']['ledger']
        for r in records:
            if r['kind']=='certificate':
                current=[x for x in r['refs'] if records[x]['kind']=='experience'
                         and json.loads(records[x]['body'])['tick']==json.loads(r['body'])['tick']]
                for key in current:
                    self.assertIn(key,r['deps'])

    def test_old_hypotheses_are_retained_not_overwritten(self):
        self.assertGreaterEqual(len(self.row['trace']['unresolved_epochs']),3)
        self.assertTrue(all(e['candidates'] for e in self.row['trace']['unresolved_epochs']))

    def test_same_information_plain_log(self):
        other=timeline(0,'plain')
        self.assertEqual(self.row['counts'],other['counts'])
        self.assertEqual(self.row['trace'],other['trace'])

    def test_every_review_respects_same_budget(self):
        for a in self.row['trace']['audits']:
            cost=a['review']['cost']
            self.assertLessEqual(cost['reads'],8)
            self.assertLessEqual(cost['probes'],8)
            self.assertLessEqual(cost['ops'],100000)
            self.assertLessEqual(cost['bytes'],65536)

    def test_initially_uninformed(self):
        q=Queen()
        self.assertEqual(len(q.H),588)
        self.assertFalse(q.valid())
        self.assertEqual(q.experiences,[])

    def test_hidden_parameters_absent_from_port_surface(self):
        p=Port(World(3))
        for name in ('truth','_bias','_gain','_positions','fault_schedule'):
            self.assertFalse(hasattr(p,name))


class IdentityTests(unittest.TestCase):
    def test_symmetric_histories_equal_uncertainty(self):
        p={'observations':[{'local_effect':i%7,'paths':[i%7,i%7]} for i in range(10)]}
        self.assertEqual(Queen().attribute(p)['probability'],[0.5,0.5])

    def test_opposite_authors_same_observation(self):
        p=pressure_cases()['symmetry']
        self.assertTrue(p['identical_public_view'])
        self.assertEqual(p['probabilities'],p['swapped'])

    def test_anonymous_permutation_equivariance(self):
        for i in range(10):
            rows=[{'local_effect':1,'paths':[1,2 if j==i else 1]} for j in range(10)]
            swapped=[{'local_effect':r['local_effect'],'paths':r['paths'][::-1]} for r in rows]
            a=Queen().attribute({'observations':rows})
            b=Queen().attribute({'observations':swapped})
            self.assertEqual(a['probability'],b['probability'][::-1])

    def test_all_ten_witness_locations_exact_read_bound(self):
        unique=0
        for i in range(10):
            p={'observations':[{'local_effect':0,'paths':[0,int(j==i)]} for j in range(10)]}
            unique += Queen().attribute(p)['status']=='unique'
        self.assertEqual(unique,8)

    def test_masking_does_not_borrow_hidden_self_history(self):
        p={'observations':[{'local_effect':1,'paths':[1,2]} for _ in range(10)]}
        q=Queen('masked')
        self.assertEqual(q.attribute(p)['probability'],[0.5,0.5])

    def test_ids_hashes_authors_and_reference_links_rejected(self):
        for field in ('author_id','instance','fingerprint','refs','true_author'):
            with self.assertRaises(ValueError):
                Queen().attribute({'observations':[],field:'secret'})
            with self.assertRaises(ValueError):
                Queen().attribute({'observations':[{'local_effect':1,'paths':[1,2],field:'secret'}]})

    def test_inconsistent_port_abstains(self):
        p={'observations':[{'local_effect':3,'paths':[1,2]}]}
        self.assertEqual(Queen().attribute(p)['status'],'inconsistent')

    def test_identity_and_functional_scores_are_independent(self):
        row=timeline(1,'masked')
        self.assertEqual(row['counts']['future_checks'],row['counts']['future_correct'])
        self.assertEqual(row['counts']['attribution_unique'],0)


class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=pressure_cases()

    def test_wrong_revision_rollback_restores_actual_state(self):
        self.assertTrue(self.p['misleading_reference']['restored'])
        self.assertEqual(self.p['misleading_reference']['status'],'rolled_back')
        self.assertFalse(self.p['misleading_reference']['permit'])

    def test_detectable_out_of_family_refused(self):
        self.assertTrue(self.p['nonlinear_sensor']['blocked'])

    def test_revoke_blocks_task_execution(self):
        self.assertTrue(self.p['revocation']['execution_denied'])

    def test_correct_review_can_reference_invalid_claim(self):
        self.assertTrue(self.p['revocation']['review_survives'])

    def test_latent_fault_can_pass_but_later_revokes(self):
        p=self.p['latent_motor']
        self.assertTrue(p['initially_accepted'])
        self.assertTrue(p['future_action_failed'])
        self.assertFalse(p['post_review_valid'])

    def test_wrong_causal_reference_failure_is_not_hidden(self):
        self.assertTrue(self.p['lying_causal_port']['incorrectly_certain'])

    def test_binding_change_invalidates_permit(self):
        q,w=Queen(),World(8)
        q.review(Port(w),bootstrap=True)
        self.assertTrue(q.valid())
        q._judge=Judge()
        self.assertFalse(q.valid())
        with self.assertRaises(PermissionError):
            q.decide(0,1)

    def test_budget_overflow_is_explicit(self):
        b=Budget()
        with self.assertRaises(RuntimeError):
            b.spend('probes',9)

    def test_consistent_evidence_does_not_revoke(self):
        q,w=Queen(),World(5)
        q.review(Port(w),bootstrap=True)
        cert=q.certificate
        q.experience(Port(w),0,2)
        self.assertNotIn(cert,q.ledger.invalid)

    def test_rejected_revision_can_be_retried_on_new_evidence(self):
        q,w=Queen(),World(42)
        w.lie_at_zero=True
        q.review(Port(w),bootstrap=True)
        w.lie_at_zero=False
        result=q.experience(Port(w),0,2)
        self.assertTrue(result['acted'])
        self.assertTrue(result['success'])
        self.assertEqual(q.rollbacks,1)


if __name__=='__main__':
    unittest.main()
