"""New R37 mechanism/counterexample tests. These are not the missing frozen tests.
Some tests confirm disclosed counterexamples; a green suite is not an RSI result.
"""
import copy
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from itertools import permutations,product
import json,lzma,math
from pathlib import Path
from random import Random
import unittest
from r28_r31.space import CausalSpace,Response
from r28_r31.study import Bundle,INITIAL
from r32_r37.space import MeasuredSpace,Atlas,rho,finite_best
from r32_r37.closure import refine,witness,learn_closure,STATES,ACTIONS
from r32_r37.experiment import fixture,episode
from r32_r37.recovery.verify_recovery import pair_partition,execute_word,verify_episode,closure_check,ledger_check

class MiniOwner:
    """Isolated metric tests use the REAL inherited ledger; not a trajectory substitute."""
    def __init__(self):
        from vendor.library_m8.core import Ledger
        self.ledger=Ledger()
    def add(self,kind,data,refs=(),deps=()):return self.ledger.add(kind,'test',data,tuple(refs),tuple(deps))
    def read(self,i):
        if i in self.ledger.invalid:raise PermissionError('withdrawn')
        return json.loads(self.ledger.records[i].body)

def rr(loss=0,sig=0,task=0,req=0):return Response(loss,(sig,),task,(req,))

def setup_space(cols=None,weights=None,metric='measured'):
    q=MiniOwner();pool=[Bundle(i) for i in range(3)]
    cols=cols or [[rr(0,0),rr(.2,1),rr(.3,2)],[rr(.4,2),rr(.1,1),rr(.2,0)],[rr(.2,0),rr(.5,1),rr(.6,2)]]
    supports=[q.add('observed',{'index':j}) for j in range(len(cols))]
    context={'protocol':'test-v1','budget':12}
    s=MeasuredSpace(q,pool,cols,supports,context,metric,weights)
    return q,pool,cols,supports,context,s

class MetricTests(unittest.TestCase):
    def test_permutation_invariant(self):
        q,p,c,s,ctx,base=setup_space()
        for perm in permutations(range(3)):
            obj=MeasuredSpace(q,p,[c[j] for j in perm],[s[j] for j in perm],ctx)
            self.assertEqual(obj.matrix(),base.matrix());self.assertEqual(obj.risks(),base.risks())
    def test_point_permutation_equivariant(self):
        q,p,c,s,ctx,base=setup_space()
        for perm in permutations(range(3)):
            obj=MeasuredSpace(q,[p[i] for i in perm],[[col[i] for i in perm] for col in c],s,ctx)
            for i,j in product(range(3),repeat=2):self.assertEqual(obj.distance(i,j),base.distance(perm[i],perm[j]))
    def test_metric_axioms_and_loss_bound(self):
        rng=Random(0)
        for trial in range(24):
            cols=[[rr(rng.randrange(11)/10,rng.randrange(3),rng.randrange(2),rng.randrange(3)) for _ in range(3)] for j in range(3)]
            *_,s=setup_space(cols,[1,2,3]);risks=s.risks()
            for i,j,k in product(range(3),repeat=3):
                self.assertEqual(s.distance(i,j),s.distance(j,i));self.assertEqual(s.distance(i,i),0)
                self.assertLessEqual(s.distance(i,k),s.distance(i,j)+s.distance(j,k))
                self.assertLessEqual(abs(risks[i]-risks[j]),s.distance(i,j))
    def test_graph_information_equivalence(self):
        *_,s=setup_space();self.assertEqual(s.matrix(),s.matrix('graph'))
    def test_compression_preserves_mass(self):
        cols=[[rr(0,0),rr(0,1),rr(0,2)]]*3
        *_,s=setup_space(cols,[1,2,4]);self.assertEqual(s.compressed_pieces[0][1],7);self.assertEqual(s.compressed,s._distances)
    def test_duplicate_receipt_idempotent(self):
        q,p,c,s,ctx,base=setup_space();obj=MeasuredSpace(q,p,c+[c[0]],s+[s[0]],ctx)
        self.assertEqual(obj.matrix(),base.matrix());self.assertEqual(obj.mass,base.mass)
    def test_inconsistent_duplicate_rejected(self):
        q,p,c,s,ctx,_=setup_space()
        with self.assertRaises(ValueError):MeasuredSpace(q,p,c+[c[1]],s+[s[0]],ctx)
    def test_negative_weights_rejected(self):
        with self.assertRaises(ValueError):setup_space(weights=[1,-1,1])
    def test_zero_total_mass_rejected(self):
        with self.assertRaises(ValueError):setup_space(weights=[0,0,0])
    def test_zero_weight_coordinate_does_not_change_metric(self):
        q,p,c,s,ctx,base=setup_space();ref=q.add('extra',{})
        obj=MeasuredSpace(q,p,c+[[rr(1),rr(0),rr(.5)]],s+[ref],ctx,weights=[1,1,1,0]);self.assertEqual(obj.matrix(),base.matrix())
    def test_new_constant_evidence_changes_measure_not_a_bug(self):
        q,p,c,s,ctx,base=setup_space();ref=q.add('new_actual_protocol_atom',{})
        obj=MeasuredSpace(q,p,c+[[rr(0)]*3],s+[ref],ctx)
        self.assertEqual(obj.distance(0,1),base.distance(0,1)*Fraction(3,4))
    def test_revocation_stops_cached_and_graph_reads(self):
        q,p,c,s,ctx,base=setup_space();old=q.ledger.records[s[0]].body;q.ledger.revoke(s[0],'test')
        for read in (lambda:base.distance(0,1),lambda:base.matrix('graph'),base.risks):
            with self.assertRaises(PermissionError):read()
        h=q.add('history',{},refs=(s[0],));self.assertNotIn(h,q.ledger.invalid);self.assertEqual(q.ledger.records[s[0]].body,old)
    def test_withdrawn_atom_cannot_form_new_space(self):
        q,p,c,s,ctx,_=setup_space();q.ledger.revoke(s[0],'test')
        with self.assertRaises(PermissionError):MeasuredSpace(q,p,c,s,ctx)
    def test_context_change_rejected(self):
        *_,s=setup_space()
        with self.assertRaises(PermissionError):s.require({'protocol':'test-v1','budget':13})
    def test_partial_response_column_rejected(self):
        with self.assertRaises(ValueError):setup_space([[rr(0),rr(.1)]])
    def test_invalid_loss_rejected(self):
        for v in (float('nan'),float('inf'),1.01,-.01):
            with self.assertRaises(ValueError):setup_space([[rr(v)]*3])
    def test_zero_equivalence_split_by_new_evidence(self):
        q,p,c,s,ctx,base=setup_space([[rr(0)]*3]);self.assertEqual(len(set(base.groups)),1)
        ref=q.add('new',{});new=MeasuredSpace(q,p,c+[[rr(0),rr(0,1),rr(0,1)]],s+[ref],ctx)
        self.assertEqual(len(set(new.groups)),2)
    def test_original_order_counterexample(self):
        c=[[rr(0,a) for a in col] for col in ((0,0,1),(0,1,0),(0,1,2))]
        q,p,c,s,ctx,_=setup_space(c)
        first=CausalSpace(q,p,c,s);second=CausalSpace(q,p,[c[j] for j in (2,0,1)],[s[j] for j in (2,0,1)])
        self.assertNotEqual(first.distance(0,1),second.distance(0,1));self.assertEqual(len(set(first.groups)),len(set(second.groups)))
    def test_atlas_context_refusal(self):
        q,p,c,s,ctx,a=setup_space();b=MeasuredSpace(q,p,c,s,dict(ctx,budget=13));atlas=Atlas(q);atlas.append(a);atlas.append(b)
        self.assertFalse(atlas.overlap(0,1)['comparable'])
    def test_atlas_shared_response_conflict(self):
        q,p,c,s,ctx,a=setup_space();new=copy.deepcopy(c);new[0][0]=rr(.9)
        b=MeasuredSpace(q,p,new,s,ctx);atlas=Atlas(q);atlas.append(a);atlas.append(b)
        with self.assertRaises(ValueError):atlas.overlap(0,1)
    def test_atlas_metric_not_checked_counterexample(self):
        # Disclosed limitation: frozen Atlas compares response records, NOT metric conventions.
        q,p,c,s,ctx,a=setup_space();b=MeasuredSpace(q,p,c,s,ctx,metric='hamming');atlas=Atlas(q);atlas.append(a);atlas.append(b)
        self.assertTrue(atlas.overlap(0,1)['comparable']);self.assertNotEqual(a.distance(0,1),b.distance(0,1))

class TableEngine:
    def __init__(self,pool,table):self.rows={b.key:r for b,r in zip(pool,table)};self.cost=Counter()
    def run(self,b,j):self.cost['calls']+=1;return rr(self.rows[b.key][j])

class FiniteTests(unittest.TestCase):
    def run_case(self,table,proposer=INITIAL,epsilon=0):
        pool=[Bundle(i) for i in range(len(table))];engine=TableEngine(pool,table)
        chosen,cert=finite_best(pool,engine,range(len(table[0])),proposer,epsilon)
        risks=[sum(Fraction(str(x)) for x in row)/len(row) for row in table]
        index=next(i for i,b in enumerate(pool) if b.key==chosen.key)
        self.assertLessEqual(risks[index],min(risks)+epsilon);self.assertLessEqual(cert['queries'],len(table)*len(table[0]))
        return index,cert
    def test_all_binary_three_by_two_tables(self):
        for flat in product((0,1),repeat=6):self.run_case([flat[:2],flat[2:4],flat[4:]])
    def test_schedule_cannot_change_exact_optimum(self):
        rng=Random(1)
        for _ in range(24):
            table=[[rng.randrange(11)/10 for j in range(4)] for i in range(4)]
            a,_=self.run_case(table);b,_=self.run_case(table,Bundle('visits'));self.assertEqual(a,b)
    def test_exact_tie_keeps_parent(self):self.assertEqual(self.run_case([[.2]*3]*3)[0],0)
    def test_epsilon_certificate(self):self.run_case([[.9,.1],[.4,.4],[.7,.2]],epsilon=Fraction(1,10))
    def test_future_bank_reversal_is_possible(self):
        chosen,_=self.run_case([[.8,.8],[.1,.1]])
        self.assertEqual(chosen,1);self.assertGreater([.1,.9][chosen],[.1,.9][0])
    def test_fresh_four_block_hoeffding_radius_cannot_certify(self):
        self.assertGreater(math.sqrt(2*math.log(40)/4),1.)
    def test_invalid_loss_fails(self):
        pool=[Bundle(0),Bundle(1)]
        with self.assertRaises(ValueError):finite_best(pool,TableEngine(pool,[[2,2],[2,2]]),range(2),INITIAL)

class ClosureTests(unittest.TestCase):
    def test_small_machine_exhaustive_partition(self):
        states=(0,1);actions=(0,1)
        for nxt in product(states,repeat=4):
            T=dict(zip(product(states,actions),nxt))
            for effects in product((0,1),repeat=4):
                O=dict(zip(product(states,actions),effects));g,h=refine(T,O,states,actions);bad=pair_partition(T,O,states,actions)
                self.assertEqual(g[0]!=g[1],(0,1) in bad);self.assertLessEqual(len(h),4)
    def test_random_larger_machine_partition(self):
        rng=Random(0);states=tuple(range(6));actions=(0,1)
        for _ in range(36):
            T={(s,a):rng.randrange(6) for s,a in product(states,actions)};O={(s,a):rng.randrange(2) for s,a in T}
            g,h=refine(T,O,states,actions);bad=pair_partition(T,O,states,actions)
            for i,j in product(states,repeat=2):self.assertEqual(g[i]!=g[j],(min(i,j),max(i,j)) in bad)
    def test_missing_transition_rejected(self):
        with self.assertRaises(ValueError):refine({(0,0):0},{(0,0):0},(0,1),(0,))
    def test_outside_transition_rejected(self):
        with self.assertRaises(ValueError):refine({(0,0):1},{(0,0):0},(0,),(0,))
    def test_two_step_witness(self):
        T={(0,0):1,(1,0):2,(2,0):2};O={(0,0):0,(1,0):0,(2,0):1}
        word=witness(0,1,T,O,(0,));self.assertEqual(word,(0,0))
        self.assertNotEqual(execute_word(0,word,T,O),execute_word(1,word,T,O))
    def test_equivalent_states_have_no_witness(self):
        T={(0,0):1,(1,0):0};O={(0,0):0,(1,0):0};self.assertIsNone(witness(0,1,T,O,(0,)))

class ActualQueenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.q,cls.w,cls.p=fixture(1);cls.c,cls.cells=learn_closure(cls.q,cls.p)
    def test_actual_complete_cell_count(self):self.assertEqual(self.cells,4802)
    def test_actual_multistep_witness(self):self.assertIsNotNone(self.c.long_witness)
    def test_last_action_memory_needed(self):self.assertTrue(self.c.memory_conflicts)
    def test_actual_goal_execution(self):
        r=self.q.causal_act(self.p,0,4);self.assertTrue(r['correct']);self.assertTrue(r['executed'])
    def test_emitter_binding_change_rejected(self):
        old=self.q._emit;self.q._emit=lambda x:x
        try:
            with self.assertRaises(PermissionError):self.c.require()
        finally:self.q._emit=old
    def test_offsets_change_rejected(self):
        old=self.q.offsets[:];self.q.offsets[0]=(old[0]+1)%7
        try:
            with self.assertRaises(PermissionError):self.c.require()
        finally:self.q.offsets=old
    def test_last_mutation_rejected(self):
        old=self.q.last;self.q.last=(old+1)%7
        try:
            with self.assertRaises(PermissionError):self.c.require()
        finally:self.q.last=old
    def test_port_swap_rejected(self):
        from r28_r31.study import Port
        with self.assertRaises(PermissionError):self.q.causal_act(Port(self.w),0,1)
    def test_quotient_is_immutable(self):
        with self.assertRaises(TypeError):self.c.quotient[0,(0,0)]=((1,0),0)
    def test_z_revoke_recover_actual_entry(self):
        q,c,p=self.q,self.c,self.p;old_id=(id(q),id(q.ledger));root=c.rows[0]['observation'];text=q.ledger.records[root].body;q.ledger.revoke(root,'test')
        with self.assertRaises(PermissionError):q.causal_act(p,0,1)
        nc,n=learn_closure(q,p,c.rows);self.assertEqual(n,1);self.assertEqual(old_id,(id(q),id(q.ledger)))
        self.assertEqual(text,q.ledger.records[root].body);self.assertIn(c.license,q.ledger.invalid);self.assertNotIn(nc.license,q.ledger.invalid)
        self.assertTrue(q.causal_act(p,1,5)['correct'])

class VerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[2]/'results/r32_r37_recovery/development/0_measured.json.xz'
        cls.r=json.loads(lzma.decompress(path.read_bytes()))
    def test_real_development_archive_passes(self):self.assertTrue(verify_episode(self.r)['valid'])
    def test_corrupt_transition_rejected(self):
        r=copy.deepcopy(self.r);r['closure']['rows'][0]['output'][0]=1
        with self.assertRaises(ValueError):verify_episode(r)
    def test_corrupt_ledger_dependency_rejected(self):
        r=copy.deepcopy(self.r);r['ledger'][5]['deps']=[999999]
        with self.assertRaises(ValueError):verify_episode(r)
    def test_corrupt_summary_rejected(self):
        r=copy.deepcopy(self.r);r['summary']['updates']+=1
        with self.assertRaises(ValueError):verify_episode(r)
    def test_corrupt_metric_rejected(self):
        r=copy.deepcopy(self.r);r['rounds'][0]['space']['distance_rationals'][0][1]='9'
        with self.assertRaises(ValueError):verify_episode(r)
    def test_corrupt_gain_rejected(self):
        r=copy.deepcopy(self.r);r['rounds'][0]['gamma_previous']+=1
        with self.assertRaises(ValueError):verify_episode(r)
    def test_corrupt_bisimulation_rejected(self):
        r=copy.deepcopy(self.r);r['closure']['groups'][0][1]=1234
        with self.assertRaises((ValueError,KeyError)):verify_episode(r)

class OverlapGuardTests(unittest.TestCase):
    def test_cross_metric_guard_refuses(self):
        from .guarded_atlas import checked_overlap
        q,p,c,s,ctx,a=setup_space();b=MeasuredSpace(q,p,c,s,ctx,metric='hamming')
        self.assertFalse(checked_overlap(a,b)['comparable'])
    def test_exact_shared_measure_transport(self):
        from .guarded_atlas import checked_overlap
        q,p,c,s,ctx,a=setup_space();b=MeasuredSpace(q,p,c[::-1],s[::-1],ctx)
        r=checked_overlap(a,b);self.assertEqual(r['status'],'EXACT_ON_COMMON_MEASURE')
        index={b.key:i for i,b in enumerate(a.pool)}
        self.assertEqual(r['distance_rationals'],[[str(a.distance(index[p],index[q])) for q in r['points']] for p in r['points']])
    def test_empty_overlap_not_geometry(self):
        from .guarded_atlas import checked_overlap
        q,p,c,s,ctx,a=setup_space();other=[q.add('new',{}) for _ in c];b=MeasuredSpace(q,p,c,other,ctx)
        self.assertEqual(checked_overlap(a,b)['status'],'NO_POSITIVE_OVERLAP')
    def test_different_ledger_namespace_refused(self):
        from .guarded_atlas import checked_overlap
        *_,a=setup_space();*_,b=setup_space()
        with self.assertRaises(ValueError):checked_overlap(a,b)

class DriftTests(unittest.TestCase):
    def test_stationarity_counterexample_revokes_actual_control(self):
        q,w,p=fixture(0);c,n=learn_closure(q,p)
        d,k,op,t,g=w.parameters;w.parameters=(d,k,op,t,tuple(1+x%6 for x in g))
        positions=q.decode(p.sense())[0];goal=(positions[0]+1)%7
        r=q.causal_act(p,0,goal)
        self.assertTrue(r['executed']);self.assertFalse(r['correct']);self.assertIn(c.license,q.ledger.invalid)
        with self.assertRaises(PermissionError):q.causal_act(p,0,goal)

class SequenceMetricTests(unittest.TestCase):
    def test_shortest_word_distance(self):
        from .sequence_metric import sequence_metric
        Q={(0,0):(0,1),(1,0):(0,2),(2,0):(1,2)}
        r=sequence_metric(Q);self.assertEqual(r['matrix'][0][1],'1/2');self.assertEqual(r['matrix'][0][2],'1');self.assertTrue(r['is_metric_on_quotient'])
    def test_equivalent_distinct_states_zero(self):
        from .sequence_metric import sequence_metric
        r=sequence_metric({(0,0):(0,1),(1,0):(0,0)});self.assertEqual(r['matrix'][0][1],'0');self.assertFalse(r['is_metric_on_quotient'])
    def test_discount_scope(self):
        from .sequence_metric import sequence_metric
        for x in (0,1,2):
            with self.assertRaises(ValueError):sequence_metric({(0,0):(0,0)},x)
    def test_complete_scope_required(self):
        from .sequence_metric import sequence_metric
        with self.assertRaises(ValueError):sequence_metric({(0,0):(0,1),(1,1):(1,0)})
    def test_actual_development_quotient(self):
        from .sequence_metric import sequence_metric
        p=Path(__file__).resolve().parents[2]/'results/r32_r37_recovery/development/0_measured.json.xz';r=json.loads(lzma.decompress(p.read_bytes()))
        Q={(c,tuple(a)):(tuple(o),t) for c,a,o,t in r['closure']['quotient']};v=sequence_metric(Q)
        self.assertTrue(v['is_metric_on_quotient']);self.assertTrue(v['fixed_point_and_ultrametric_checked'])

if __name__=='__main__':unittest.main(verbosity=2)
