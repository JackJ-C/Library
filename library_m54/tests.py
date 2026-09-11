import copy,inspect,json,unittest
from random import Random
from .grammar import *
from .queen import Queen,Budget,Limit,NotLicensed,predicate_signature
from .world import World,Port
from .study import trajectory,parameters

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.life=trajectory(0)
    def setup_world(self):
        w=World(parameters(1));q=Queen(1);q.repair(Port(w));return q,w,Port(w)
    def test_continuity(self):
        c=self.life['counts'];self.assertTrue(c['same_instance'] and c['history_unchanged']);self.assertGreaterEqual(c['post_boot_revisions'],3)
    def test_structure_changes(self):self.assertGreaterEqual(self.life['counts']['structure_revisions'],1)
    def test_actual_heldout_transfer(self):self.assertEqual(self.life['counts']['future_correct'],1176)
    def test_heldout_not_in_fit(self):
        for rec in self.life['ledger']:
            if rec['kind']=='intention':self.assertEqual(json.loads(rec['body'])['state'][0]%2,0)
    def test_predictions_before_observations(self):
        records=self.life['ledger']
        for r in records:
            if r['kind']=='observation':
                k=json.loads(r['body'])['intention'];self.assertLess(k,r['seq']);self.assertEqual(records[k]['kind'],'intention');self.assertIn('predicted_after',json.loads(records[k]['body']))
    def test_no_gold_feedback_arguments(self):
        for name in ('act','trial','repair','sample','decide'):
            signature=inspect.signature(getattr(Queen,name))
            self.assertTrue(set(signature.parameters).isdisjoint({'correct','success','fault','author','stage','scene','level'}))
    def test_observation_schema_rejects_gold(self):
        q,w,p=self.setup_world()
        with self.assertRaises(ValueError):q.decode(dict(w.sense(),correct=True))
    def test_port_has_no_truth(self):
        p=Port(World(parameters(0)))
        for k in ('level','gain','parameters','bias','truth'):self.assertFalse(hasattr(p,k))
    def test_generic_atoms_not_full_laws(self):
        self.assertTrue(all(e[0] in ('equals','less') for e,m in ATOMS))
        self.assertGreater(len(ATOMS),20)
    def test_compile_matches_tree(self):
        for r in self.life['revisions']:
            fn=compile_tree(r['new'])
            for s in STATES:
                for a in (0,1,6):self.assertEqual(fn(*s,a),predict(r['new'],s)*a%7)
    def test_no_constant_gain_can_fit_new_conditions(self):
        reports=[json.loads(r['body']) for r in self.life['ledger'] if r['kind']=='model_revision']
        self.assertTrue(any(r['same_command_conflicting_effects'] is not None for r in reports))
    def test_isolating_interventions_exist(self):
        rows=[v for r in self.life['revisions'] for b in r['validation'] for v in b['observations'] if 'contrast_axis' in v]
        self.assertTrue({1,2,3} <= {r['contrast_axis'] for r in rows})
        self.assertTrue({1,2} <= {r['command'] for r in rows})
    def test_validation_is_not_true_label_input(self):
        qsrc=inspect.getsource(Queen)
        self.assertNotIn('gain_gold',qsrc);self.assertNotIn('correct_gold',qsrc)
    def test_no_regression_in_unchanged_physics(self):self.assertEqual(self.life['counts']['regressions'],0)
    def test_noise_and_own_cause_separate(self):
        cs=self.life['component_changes'];self.assertEqual(sum(r['component']=='Workers' for r in cs),1);self.assertEqual(sum(r['component']=='own_emission' for r in cs),1)
    def test_healthy_calibration_not_replaced(self):
        q,w,p=self.setup_world();old=(q._emit,q.offsets,q.calibration);q.calibrate(p,Budget());self.assertEqual(old,(q._emit,q.offsets,q.calibration))
    def test_withdrawal_blocks_action_not_sensing(self):
        q,w,p=self.setup_world();cal=q.calibration;s=q.revisions[-1]['support'][0];q.ledger.revoke(s,'withdraw test')
        n=w.cost['task_moves'];self.assertFalse(q.act(p,0,3)['executed']);self.assertFalse(q.execute(p,0,3)['executed'])
        with self.assertRaises(NotLicensed):q.decide(p.sense(),0,3)
        self.assertEqual(w.cost['task_moves'],n);self.assertNotIn(cal,q.ledger.invalid)
    def test_revoke_does_not_erase_actual_command(self):
        q,w,p=self.setup_world();q.prepare(p,(0,2,0,0));e=q.act(p,0,1);q.invalidate('later theory refuted')
        self.assertNotIn(e['intention'],q.ledger.invalid);self.assertIn('issued',q.read(e['intention']))
    def test_wrong_history_can_be_reviewed(self):
        q,w,p=self.setup_world();old=q.scope;r=q.add('reflection',{'old_unsupported':True},refs=(old,));q.ledger.revoke(old,'x');self.assertNotIn(r,q.ledger.invalid)
    def test_budget_enforced(self):
        b=Budget()
        for k,n in [('probes',181),('ops',12000001),('reads',5001),('bytes',5000001)]:
            with self.assertRaises(Limit):b.charge(k,n)
    def test_identity_separate(self):
        c=self.life['counts'];self.assertEqual(c['attribution_distinct_correct'],c['attribution_distinct_total']);self.assertEqual(c['attribution_symmetric_correct'],c['attribution_symmetric_total'])
    def test_identity_permutation(self):self.assertTrue(all(r['permutation_ok'] for r in self.life['attribution']))
    def test_identity_metadata_rejected(self):
        q,w,p=self.setup_world();q.prepare(p,(0,2,0,0));e=q.act(p,0,1)
        with self.assertRaises(ValueError):q.attribute(e['intention'],{'paths':[],'author':0})
    def test_zero_command_is_not_automatically_failure(self):
        q,w,p=self.setup_world();q.prepare(p,(0,2,0,0));e=q.act(p,0,0);self.assertFalse(e['mismatch']);self.assertTrue(q.valid())
    def test_dev_and_confirmation_conditions_disjoint(self):
        for seed in range(4):self.assertIn(parameters(seed)[0],(0,1,2))
        for seed in (22000,23000):self.assertIn(parameters(seed,True)[0],(3,4,5,6))
    def test_old_prediction_content_not_overwritten(self):
        c=self.life['counts'];self.assertTrue(c['history_unchanged']);self.assertTrue(any(s['reinterpretation'] for s in self.life['stages']))

if __name__=='__main__':unittest.main()
