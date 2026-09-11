"""Development seeds only; unit/property tests are not independent natural trajectories."""
import copy
from itertools import permutations
from random import Random
import inspect,json,unittest
from library_m37.core import NotLicensed,probe_packet
from .core import (MODELS,LINEAR,Queen,Budget,fit_pairs,common_inverse,compile_control,
                   sensory_projection,canonical)
from .world import AnonymousPort
from .study import make,trajectory,task,pressures


class SourceTests(unittest.TestCase):
    def learned(self,seed=0):
        q,w,p=make(seed);w.set_scene(1,0);q.activate(1,0);r=q.learn(p)
        obs=[x for x in q.book.ledger.records if x.kind=='anonymous_effects'][-1]
        packet=json.loads(obs.body)['data']['packet']
        ints=[json.loads(x.body)['data'] for x in q.book.ledger.records if x.kind=='explore_intention']
        commands=[(x['object'],x['command']) for x in ints]
        return q,w,p,r,packet,commands

    def test_no_external_witness_argument(self):
        self.assertEqual(list(inspect.signature(Queen.learn).parameters),['self','port'])
        self.assertEqual(list(inspect.signature(Queen.infer).parameters),['self','budget'])

    def test_real_three_sources_executed(self):
        q,w,p,r,packet,commands=self.learned()
        self.assertTrue(all(len(round)==3 for round in p.private_log[-1]['rounds']))
        pairs=fit_pairs(commands,packet)
        self.assertIn((p.private_log[-1]['true_source_index'],w.permutation),pairs)

    def test_six_anonymous_orders_equivariant(self):
        *_,packet,commands=self.learned()
        old=set(fit_pairs(commands,packet))
        for order in permutations(range(3)):
            new=set(fit_pairs(commands,{'paths':[packet['paths'][i] for i in order]}))
            self.assertEqual(new,{(order.index(i),m) for i,m in old})

    def test_absolute_positions_not_identity_cue(self):
        *_,packet,commands=self.learned()
        old=fit_pairs(commands,packet)
        for shift in range(5):
            p=copy.deepcopy(packet)
            for path in p['paths']:
                for frame in path:
                    for side in ('before','after'):
                        frame[side]=[[(x+shift)%5 for x in worker] for worker in frame[side]]
            self.assertEqual(old,fit_pairs(commands,p))

    def test_no_author_command_fingerprint_or_graph_in_public(self):
        *_,p,commands=self.learned()
        for key in ('actor','id','commands','refs','fingerprint','true_source_index'):
            v=copy.deepcopy(p);v[key]=0
            with self.assertRaises(ValueError):sensory_projection(v)
            v=copy.deepcopy(p);v['paths'][0][0][key]=0
            with self.assertRaises(ValueError):sensory_projection(v)

    def test_intention_precedes_actual_observation(self):
        q,w,p,r,_,_=self.learned()
        for a in r['attempts']:self.assertLess(a['intent'],a['observation'])

    def test_missing_journal_keeps_model_uncertainty(self):
        q,w,p=make(0,'masked');w.set_scene(1,0);q.activate(1,0);r=q.learn(p)
        self.assertEqual(len(r['models']),24)
        self.assertEqual(r['inverse'],[0,None,None,None,None])

    def test_competing_source_with_same_effect_does_not_force_ownership(self):
        p=pressures()['echo_equal']
        self.assertEqual(p['source_options'],[0,1,2])
        self.assertTrue(p['complete']);self.assertTrue(all(r['correct'] for r in p['test']))

    def test_different_echo_maps_require_abstention(self):
        p=pressures()['echo_different']
        self.assertEqual(p['source_options'],[0,1,2])
        self.assertFalse(p['complete'])
        self.assertTrue(any(not r['executed'] for r in p['test']))
        self.assertTrue(all(not r['executed'] or r['correct'] for r in p['test']))


class ControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.row=trajectory(0,'library')

    def test_same_queen_continuous_three_or_more_revisions(self):
        c=self.row['counts'];self.assertEqual(c['same_object'],1)
        self.assertEqual(c['history_preserved'],1);self.assertGreaterEqual(c['control_revisions'],3)
        self.assertEqual(len(self.row['stages']),16)

    def test_source_evidence_enters_actual_control(self):
        for stage in self.row['stages']:
            causal=stage['causal']
            if causal:
                f=causal['arms']['factual'];r=causal['arms']['restore'];cut=causal['arms']['remove_source_constraints']
                self.assertEqual([x['command'] for x in f],[x['command'] for x in r])
                self.assertEqual(sum(x['correct'] for x in cut),2)
                self.assertTrue(causal['same_instance'])

    def test_nonlinear_model_is_executed_not_only_described(self):
        stages=[s for s in self.row['stages'] if s['representation']=='finite_permutation_table' and s['learning']]
        self.assertTrue(stages)
        for s in stages:self.assertTrue(all(r['correct'] for r in s['future']))

    def test_all_24_models_independent_inverse_identity(self):
        for m in MODELS:
            fn=compile_control(common_inverse([m]))
            for target in range(5):self.assertEqual(m[fn(target)],target)

    def test_all_pair_unanimous_actions_sound(self):
        for a in MODELS:
            for b in MODELS:
                inverse=common_inverse([a,b])
                for d,u in enumerate(inverse):
                    if u is not None:self.assertEqual((a[u],b[u]),(d,d))

    def test_source_retraction_blocks_four_real_entries(self):
        self.assertTrue(all(self.row['gate'].values()))

    def test_only_binding_change_also_blocks(self):
        q,w,p=make(2);w.set_scene(0,0);q.activate(0,0);q.learn(p)
        q.selected['function']=compile_control([0,1,2,3,4])
        self.assertFalse(q.valid());self.assertFalse(q.execute('apple',2,1)['executed'])
        with self.assertRaises(NotLicensed):q.predict(probe_packet(0))

    def test_false_confidence_outside_family_is_recorded(self):
        s=pressures()['unseen_state_dependence']
        self.assertTrue(s['actual_error']);self.assertFalse(s['licence_after_observed_error'])
        self.assertFalse(s['unknown_mechanism_repaired'])

    def test_same_information_plain_marginal_strong_controls(self):
        a=self.row
        for name in ('plain','marginal'):
            b=trajectory(0,name)
            for s,t in zip(a['stages'],b['stages']):
                self.assertEqual([v['correct'] for v in s['future']],[v['correct'] for v in t['future']])
                if s['learning']:
                    self.assertEqual(s['learning']['models'],t['learning']['models'])

    def test_all_evidence_dependencies_point_backward(self):
        for r in self.row['ledger']:
            self.assertTrue(all(0<=i<r['seq'] for i in r['refs']+r['deps']))

    def test_budget_caps_and_errors(self):
        b=Budget()
        for k in ('reads','ops','probes','bytes'):
            with self.assertRaises(RuntimeError):b.charge(k,getattr(b,'max_'+k)+1)
        for s in self.row['stages']:
            if s['learning']:
                for k,v in s['learning']['cost'].items():self.assertLessEqual(v,getattr(Budget(),'max_'+k))

    def test_current_scene_not_supplied_history_index(self):
        q,w,p=make(0)
        for i in range(4):
            w.set_scene(i,i);q.activate(i,i);q.learn(p)
        q.activate(0,4);r=q.infer(Budget())
        self.assertTrue(r['read_refs']);self.assertTrue(r['groups'])
        self.assertTrue(all(json.loads(q.book.ledger.records[k].body)['data']['scene']==0 for k in r['read_refs']))

    def test_repeated_scene_reuses_model_without_probes(self):
        for s in self.row['stages'][4:8]:self.assertIsNone(s['learning'])

    def test_ledger_invalidity_is_explicit(self):
        q,w,p=make(3);w.set_scene(1,0);q.activate(1,0);q.learn(p)
        root=q.book.ledger.records[q.selected['scope']].deps[-1]
        reference=q.book.append('later_review','queen',{'old_wrong':True},refs=(root,))
        q.book.revoke(root,'withdrawn')
        self.assertFalse(q.valid());self.assertNotIn(reference,q.book.ledger.invalid)


if __name__=='__main__':unittest.main()
