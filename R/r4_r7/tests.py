"""Developer-controlled checks, not additional independent validation trajectories."""
import unittest,copy,json
from dataclasses import replace
from .study import make_queen,stress
from . import search
from .monitor import assay,rebuild_model,current_reliability,feature_key,ReliabilityModel
from library_m54.queen import NotLicensed
from src.core import Port

class LifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=stress()
    def test_known_self_counterexample_stales_model(self):
        r=self.data['nonlinear_self'];self.assertTrue(r['observed_mismatch']);self.assertEqual(r['current']['status'],'stale')
    def test_old_self_content_not_erased(self):self.assertTrue(self.data['nonlinear_self']['history_still_readable'])
    def test_nonself_knowledge_survives(self):
        r=self.data['nonlinear_self'];self.assertTrue(r['worker_preserved'] and r['world_preserved'])
    def test_unresolved_cannot_reapprove(self):
        r=self.data['nonlinear_self'];self.assertEqual(r['rediagnosis'],'unresolved');self.assertTrue(r['task_stays_closed'])
    def test_recovery_requires_new_evidence(self):self.assertTrue(self.data['nonlinear_self']['recovery_after_condition_removed'])
    def test_external_failure_not_automatically_self_failure(self):self.assertTrue(all(self.data['external_drift'].values()))
    def test_unknown_initial_self(self):
        from .lifecycle import Queen
        self.assertEqual(Queen().current_self()['status'],'unknown')
    def test_binding_change_not_same_current_model(self):
        q,w=make_queen(1);q._emit=lambda a:a%7
        self.assertEqual(q.current_self()['status'],'stale');self.assertFalse(q.r_valid())
    def test_model_superseded_but_history_accessible(self):
        q,w=make_queen(1);old=q.self_permission;q.diagnose(Port(w))
        self.assertIn(old,q.ledger.invalid);self.assertFalse(q.historical_self(old)['current'])
        self.assertEqual(q.current_self()['status'],'supported')
    def test_unknown_history_rejected(self):
        q,w=make_queen(1)
        with self.assertRaises(ValueError):q.historical_self(-1)
    def test_duplicate_authorship_uncertain(self):self.assertEqual(self.data['indistinguishable_authorship']['probabilities'],[.5,.5])

class SearchTests(unittest.TestCase):
    def test_public_problem_has_no_target(self):
        p,t=search.make_problem(1);self.assertEqual(set(vars(p)),{'masks','prices','count'})
    def test_basis_identifies_each_signature(self):
        p,_=search.make_problem(1)
        for h in range(p.count):
            _,H,_=search.solve(p,search.Body(p,h),search.Program(0),search.Cost())
            self.assertEqual(H,1<<h)
    def test_program_uses_integer_semantics(self):
        f=search.Program(('/','info','price'));self.assertEqual(f((1024,128,0,0)),1024*256//129)
    def test_invalid_operator_rejected(self):
        with self.assertRaises(ValueError):search.Program(('shell',1,1))((1,1,1,1))
    def test_same_proposals_for_matched_counterfactual(self):
        pool=search.pool(0,2);self.assertEqual(pool,search.pool(0,2));self.assertEqual(len(pool),40)
    def test_generated_size_bound(self):
        self.assertTrue(all(search.nodes(p)<=15 for p in search.pool(0,2)))
    def test_constant_parent_matches_frozen(self):
        train=[search.make_problem(i) for i in range(8)];pool=search.pool(0,2)
        a,r=search.successor(0,search.Program(0),pool,train,search.Cost())
        b,s=search.successor(0,search.Program(0),pool,train,search.Cost());self.assertEqual((a,r),(b,s))
    def test_full_evaluation_budget(self):
        train=[search.make_problem(i) for i in range(8)];pool=search.pool(0,2);c=search.Cost()
        a,r=search.successor(0,search.Program(0),pool,train,c)
        self.assertEqual(len(r['selected']),6);self.assertEqual(c.full_evaluations,9)
    def test_adoption_requires_fit_and_check(self):
        train=[search.make_problem(i) for i in range(8)];pool=search.pool(0,2)
        a,r=search.successor(0,search.Program(0),pool,train,search.Cost())
        if r['accepted']:
            self.assertLess(min(r['scores'])[0],r['old_score']);self.assertLessEqual(r['adoption_check'][1],r['adoption_check'][0])
    def test_observations_filter_not_gold(self):
        p,h=search.make_problem(4);_,H,rows=search.solve(p,search.Body(p,h),search.Program(0),search.Cost())
        for row in rows:self.assertEqual(row['after'],row['before']&p.masks[row['query']][row['value']])

class MonitorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.q,cls.w=make_queen(1);cls.row=assay(cls.q,cls.w,2,ntrain=64,ntest=32,checks=8)
    def test_probabilities_in_range(self):
        for r in self.row['test']:
            for p in r['probabilities'].values():self.assertTrue(0<=p<=1)
    def test_no_identity_field_in_introspection(self):
        with self.assertRaises(ValueError):feature_key({'repeats':1,'margin':1.,'author':'Queen'})
    def test_rebuild_ignores_cached_evaluation_label(self):
        q,w=make_queen(3);row=assay(q,w,3,ntrain=16,ntest=8,checks=2)
        old=q.monitor.export();key=q.monitor.support[0];r=q.ledger.records[key]
        body=json.loads(r.body);body['consistent']=not body['consistent']
        q.ledger.records[key]=replace(r,body=json.dumps(body))
        self.assertEqual(rebuild_model(q,q.monitor.support).export(),old)
    def test_rebuild_raw_evidence_is_used(self):
        q,w=make_queen(3);row=assay(q,w,3,ntrain=16,ntest=8,checks=2)
        key=q.monitor.support[0];i,o=q.ledger.records[key].refs;rec=q.ledger.records[o];body=json.loads(rec.body)
        intent=json.loads(q.ledger.records[i].body);obj=intent['object'];goal=intent['goal']
        orig_ok=json.loads(q.ledger.records[key].body)['consistent']
        for index in (0,1):body['after']['workers'][index][obj]=(goal+int(orig_ok)+q.offsets[index])%7
        q.ledger.records[o]=replace(rec,body=json.dumps(body))
        self.assertNotEqual(rebuild_model(q,q.monitor.support).export(),q.monitor.export())
    def test_same_raw_answers_for_all_monitor_arms(self):
        self.assertEqual(len({a['raw_correct'] for a in self.row['arms'].values()}),1)
    def test_restore_and_rename_identical(self):
        arms=self.row['arms'];self.assertEqual(arms['own'],arms['restored']);self.assertEqual(arms['own'],arms['renamed'])
    def test_equal_checking_budget(self):
        self.assertTrue(all(len(self.row['arms'][a]['checked'])==8 for a in ('own','blind','transplant','restored','renamed','fixed')))
    def test_no_check_and_always_check_limits(self):
        self.assertEqual(self.row['arms']['always_check']['correct'],32)
        self.assertEqual(self.row['arms']['never_check']['correct'],self.row['arms']['own']['raw_correct'])
    def test_support_withdrawal_closes_confidence_only(self):
        q,w=make_queen(5);assay(q,w,5,ntrain=16,ntest=8,checks=2);old=q.self_permission
        q.ledger.revoke(q.monitor.support[0],'test')
        self.assertEqual(current_reliability(q,{'repeats':1,'margin':0.2})['status'],'unknown')
        self.assertNotIn(old,q.ledger.invalid)
    def test_only_prediction_precedes_test_outcome(self):
        for r,p in zip(self.row['test'],self.row['actual_primary']):self.assertLess(r['forecast'],p[0])
    def test_new_monitor_changes_no_first_order_binding(self):self.assertTrue(self.row['same_first_order_binding'])

if __name__=='__main__':unittest.main()
