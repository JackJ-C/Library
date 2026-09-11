"""以运行轨迹和错误状态为重点，不把测试数当作科学样本量。"""
import unittest
from itertools import product
from .synthesis import (Fuel, compile_plan, compile_program, digest, evaluate,
                        expand, fit, learn_macros, learn_normalized_macros, learn_plan,
                        nodes, source, tuple_tree)
from .engine import Queen,run,CHECK_DOMAIN,FUTURE


class SynthesisTests(unittest.TestCase):
    def test_old_equivalence_splits(self):
        a,b=('x',),('mul',('x',),('x',))
        self.assertEqual([evaluate(a,x) for x in (0,1)],[evaluate(b,x) for x in (0,1)])
        self.assertNotEqual(evaluate(a,-1),evaluate(b,-1))
        e=((0,0),(1,1)); n=e+((-1,1),(-2,4))
        self.assertEqual(fit(e)['expression'],a)
        self.assertEqual(fit(n)['expression'],b)
        self.assertNotEqual(fit(e)['evidence_key'],fit(n)['evidence_key'])
    def test_true_multiple_counterexamples(self):
        q,r=run(lambda x:x*x)
        self.assertTrue(r['accepted']);self.assertEqual(r['refutations'],2)
        self.assertTrue(all(q.decide(x)==x*x for x in FUTURE))
    def test_early_stopping_does_not_certify(self):
        q,r=run(lambda x:x*x,round_limit=1)
        self.assertFalse(r['accepted']);self.assertIsNone(q.certificate)
        with self.assertRaises(RuntimeError):q.decide(3)
    def test_later_candidates_retain_all_counterexamples(self):
        _,r=run(lambda x:x*(x-1)//2+2)
        for entry in r['rounds']:
            if 'lowered' not in entry: continue
            expr=tuple_tree(entry['lowered'])
            self.assertTrue(all(evaluate(expr,x)==y for x,y in entry['evidence']))
            if entry['counterexample'] is not None:
                x,y=entry['counterexample'];self.assertNotEqual(evaluate(expr,x),y)
    def test_examples_inconsistent_not_exhausted(self):
        self.assertEqual(fit(((0,0),(0,1)))['status'],'inconsistent')
    def test_empty_examples_not_permission(self):
        self.assertEqual(fit(())['status'],'insufficient_evidence')
    def test_invalid_inputs_rejected(self):
        for kwargs in ({'budget':0},{'budget':True},{'maximum':0},{'constants':('1',)}):
            with self.assertRaises(ValueError):fit(((0,0),),**kwargs)
        with self.assertRaises(ValueError):fit(((0,True),))
    def test_low_fuel_is_not_unrepresentability(self):
        e=((0,0),(1,1),(-1,1),(-2,4))
        a=fit(e,budget=7);b=fit(e,budget=64)
        self.assertEqual(a['status'],'budget_exhausted');self.assertEqual(b['status'],'fit')
        self.assertLessEqual(a['attempts'],7);self.assertLessEqual(b['attempts'],64)
    def test_node_bound_is_distinct_from_fuel(self):
        a=fit(((0,0),(1,1),(-1,1)),maximum=1,budget=100)
        self.assertEqual(a['status'],'node_bound_exhausted')
    def test_compiler_rejects_arbitrary_code(self):
        with self.assertRaises(ValueError):compile_program(('c','__import__("os")'),{})
        with self.assertRaises(ValueError):compile_program(('import',('x',),('x',)),{})
    def test_literal_guard_lowering(self):
        expr=('add',('mul',('x',),('x',)),('eq',('x',),('c',17)))
        fn=compile_program(expr,{})
        for x in range(-80,81):self.assertEqual(fn(x),x*x+int(x==17))
    def test_macro_expansion_is_real_composition(self):
        macros={'op_0':('half',('mul',('x',),('sub',('x',),('c',1))))}
        expr=('add',('call','op_0',('add',('mul',('c',3),('x',)),('c',4))),('c',1))
        lowered=expand(expr,macros);fn=compile_program(expr,macros)
        self.assertGreater(nodes(lowered),nodes(expr))
        for x in range(-80,81):self.assertEqual(fn(x),((3*x+4)*(3*x+3))//2+1)
    def test_macros_not_preloaded(self):
        macros,rows=learn_macros([]);self.assertEqual(macros,{});self.assertEqual(rows,[])
    def test_rejected_course_program_not_promoted(self):
        record={'accepted':False,'expression':('mul',('x',),('x',))}
        self.assertEqual(learn_macros([record,record])[0],{})
    def test_normalization_uses_programs_not_targets(self):
        programs=[{'accepted':True,'expression':('add',('mul',('x',),('x',)),('c',c))} for c in (0,1,2)]
        macros,rows=learn_normalized_macros(programs,CHECK_DOMAIN)
        self.assertTrue(any(all(evaluate(body,x)==x*x for x in CHECK_DOMAIN) for body in macros.values()))
        self.assertTrue(all(not r['global_equivalence_proved'] for r in rows))
    def test_plan_uses_costs_not_names(self):
        p=[{'op_0':{'attempts':10,'fit':False},'op_1':{'attempts':2,'fit':True}}]
        self.assertEqual(learn_plan(p,('op_0','op_1'))['order'],['op_1','op_0'])
    def test_plan_compiles_and_rebinds_actual_search(self):
        fn=compile_plan(['op_0']);body=('mul',('x',),('x',))
        result=fn(((0,16),(1,49),(-1,1)),{'op_0':body})
        self.assertEqual(result['status'],'fit');self.assertIn('op_0',fn.source)
        compiled=compile_program(result['expression'],{'op_0':body})
        self.assertTrue(all(compiled(x)==(3*x+4)**2 for x in CHECK_DOMAIN))
    def test_plan_cannot_drop_or_duplicate_branches(self):
        m={'op_0':('x',)}
        for order in ((),('op_0','op_0')):
            with self.assertRaises(ValueError):fit(((0,0),),m,order)
    def test_plan_no_arbitrary_source(self):
        with self.assertRaises(ValueError):compile_plan(['__import__("os")'])
    def test_final_domain_is_disjoint(self):
        self.assertFalse(set(CHECK_DOMAIN)&set(FUTURE));self.assertEqual(len(FUTURE),112)
    def test_no_target_name_in_search_signature(self):
        import inspect
        self.assertNotIn('target',inspect.signature(fit).parameters)
        self.assertNotIn('function',inspect.signature(fit).parameters)
    def test_sample_equivalence_not_global_macro_proof(self):
        a=('mul',('x',),('x',));b=('add',a,('eq',('x',),('c',71)))
        self.assertEqual([evaluate(a,x) for x in CHECK_DOMAIN],[evaluate(b,x) for x in CHECK_DOMAIN])
        self.assertNotEqual(evaluate(a,71),evaluate(b,71))


class StateTests(unittest.TestCase):
    def test_same_instance_real_deployment(self):
        q,r=run(lambda x:x*x)
        self.assertTrue(r['same_instance']);self.assertEqual(q.revision,1)
        self.assertIs(q.program.__class__,type(lambda:None))
        self.assertEqual(q.decide(8),64)
    def test_new_evidence_revokes_old_permission(self):
        q,_=run(lambda x:x*x)
        q.observe(3,9)
        self.assertIsNone(q.certificate)
        with self.assertRaises(RuntimeError):q.decide(4)
    def test_duplicate_is_not_new_evidence(self):
        q,_=run(lambda x:x*x);prior=q.certificate;events=len(q.events)
        self.assertFalse(q.observe(0,0));self.assertIs(q.certificate,prior);self.assertEqual(len(q.events),events)
    def test_contradiction_fails_closed(self):
        q,_=run(lambda x:x*x)
        with self.assertRaises(ValueError):q.observe(0,1)
        self.assertIsNone(q.certificate)
        with self.assertRaises(RuntimeError):q.decide(3)
        with self.assertRaises(ValueError):q.propose()
    def test_changed_binding_rejected(self):
        q,_=run(lambda x:x*x);q.program=compile_program(('x',),{})
        with self.assertRaises(RuntimeError):q.decide(3)
    def test_latent_unseen_branch_failure_is_real(self):
        q,r=run(lambda x:x*x+int(x==71))
        self.assertTrue(r['accepted']);self.assertNotEqual(q.decide(71),71*71+1)
        self.assertEqual(r['certificate']['scope'],'finite_checked_domain_only')
    def test_unsupported_noise_not_infinite_loop(self):
        n={0:0}
        def changing(x):
            if x==0:n[0]+=1;return n[0]%2
            return x
        with self.assertRaises(ValueError):run(changing)


if __name__=='__main__':unittest.main()
