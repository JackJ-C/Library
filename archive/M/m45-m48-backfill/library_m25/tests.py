"""本轮契约、证据独立性、生成代码和代数检查的正反测试。"""
import ast
from fractions import Fraction
from itertools import islice
from pathlib import Path
import unittest
from unittest.mock import patch
from .language import (candidate_factory, canonical, evaluate, make_builder,
                       make_search, polynomial_bank, source, synthesize, tree)
from .algebra import Poly, prove_builder, prove_search
from .experiments import (Queen, environment, learn_builders, learn_search,
                          property_cases, property_failure, search_case, search_failure,
                          strong_reference_builder, strong_reference_search, task)


class MetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports,cls.builders=learn_builders()
        cls.search_report,law=learn_search()
        cls.law=staticmethod(law)

    def test_builder_bodies_are_generated(self):
        self.assertEqual(len(self.builders),2)
        self.assertTrue(all(r['accepted'] for r in self.reports))
        self.assertTrue(all(len(r['rounds'])>1 for r in self.reports))

    def test_search_body_is_generated(self):
        self.assertTrue(self.search_report['accepted'])
        self.assertGreater(self.search_report['attempts'],1)

    def test_learner_has_no_reference_import(self):
        parsed=ast.parse(Path(__file__).with_name('language.py').read_text())
        imports=[n.module for n in ast.walk(parsed) if isinstance(n,ast.ImportFrom)]
        self.assertFalse(any('experiments' in (n or '') for n in imports))
        self.assertFalse(any('algebra' in (n or '') for n in imports))

    def test_reference_functions_not_called_during_discovery(self):
        with patch('library_m25.experiments.strong_reference_builder',side_effect=AssertionError('leak')):
            with patch('library_m25.experiments.strong_reference_search',side_effect=AssertionError('leak')):
                self.assertEqual(len(learn_builders()[1]),2)
                self.assertIsNotNone(learn_search()[1])

    def test_zero_constructor_rejected(self):
        cases=property_cases(0,range(2),(-2,0,1))
        self.assertTrue(any(property_failure(('c',0),c) for c in cases))

    def test_compiled_builder_matches_tree(self):
        fn=lambda x:x**5+13*x-59
        for level,builder in enumerate(self.builders):
            previous=self.builders[0] if level else None
            for x in range(-16,17):
                self.assertEqual(builder(fn)(x),evaluate(builder.expression,environment(fn,x,previous)))

    def test_compiled_search_matches_tree(self):
        for i in range(400,464):
            regs=search_case(i)['registers']
            self.assertEqual(self.law(**regs),evaluate(self.law.expression,regs))

    def test_same_arbitrary_function_properties(self):
        f=lambda x:abs(x-7)+(x%3)+x**4
        changed=lambda x:f(x)-19*x+111
        for x in range(-40,41):
            self.assertEqual(self.builders[1](f)(x),self.builders[1](changed)(x))

    def test_algebra_rejects_identity_builder(self):
        self.assertFalse(prove_builder(('v','fx'),0)['passed'])

    def test_algebra_rejects_zero_builder(self):
        self.assertFalse(prove_builder(('c',0),1,self.builders[0].expression)['passed'])

    def test_algebra_rejects_bad_search(self):
        self.assertFalse(prove_search(('v','p0'))['passed'])

    def test_exact_polynomial_cancellation(self):
        a,b=Poly.variable('a'),Poly.variable('b')
        self.assertTrue(((a+b)*(a-b)-(a*a-b*b)).zero())

    def test_zero_denominator_rejected(self):
        with self.assertRaises(ZeroDivisionError):self.law(0,1,4,4)

    def test_bad_variable_rejected(self):
        with self.assertRaises(ValueError):make_builder(('v','secret'))
        with self.assertRaises(ValueError):make_search(('v','secret'))

    def test_unknown_operator_rejected(self):
        with self.assertRaises(ValueError):source(('import',('c',0),('c',1)))

    def test_fuel_hard_stop(self):
        r=synthesize(candidate_factory(('x',)),(0,),lambda e,i:{'no':True},budget=1)
        self.assertEqual(r['status'],'budget_exhausted')
        self.assertEqual(r['attempts'],1)

    def test_candidate_order_deterministic(self):
        a=list(islice(candidate_factory(('a','b'),True)(),50))
        b=list(islice(candidate_factory(('a','b'),True)(),50))
        self.assertEqual(a,b)

    def test_counterexamples_preserved(self):
        for r in self.reports+[self.search_report]:
            old=[]
            for row in r['rounds']:
                self.assertTrue(set(old)<=set(row['active_before']))
                old=row['active_before']
                if row['counterexample']:old=old+[row['counterexample']['id']]

    def test_real_function_binding(self):
        q=Queen(self.builders[1],self.law);before=q.program;identity=id(q)
        raw,fn,_=task(1000,0)
        result=q.fit(raw,fn)
        self.assertTrue(result['accepted']);self.assertIsNot(q.program,before)
        self.assertEqual(id(q),identity);self.assertTrue(q.valid())

    def test_context_change_invalidates(self):
        q=Queen(self.builders[1],self.law);raw,fn,_=task(1000,0);q.fit(raw,fn)
        q.context['task']='other'
        self.assertFalse(q.valid())

    def test_bound_builder_change_invalidates(self):
        q=Queen(self.builders[1],self.law);raw,fn,_=task(1000,0);q.fit(raw,fn)
        q.builder=lambda f:f
        self.assertFalse(q.valid())

    def test_bound_search_change_invalidates(self):
        q=Queen(self.builders[1],self.law);raw,fn,_=task(1000,0);q.fit(raw,fn)
        q.search=lambda *args:0
        self.assertFalse(q.valid())

    def test_bound_program_change_invalidates(self):
        q=Queen(self.builders[1],self.law);raw,fn,_=task(1000,0);q.fit(raw,fn)
        q.program=lambda x:42
        self.assertFalse(q.valid())

    def test_failed_new_fit_does_not_retain_permission(self):
        q=Queen(self.builders[1],self.law);raw,fn,_=task(1000,0);q.fit(raw,fn)
        q.fit(lambda x:1,lambda x:x*x)
        self.assertFalse(q.valid())

    def test_two_strong_baselines_equal(self):
        raw,fn,_=task(1003,2)
        a=Queen(self.builders[1],self.law);b=Queen(strong_reference_builder,strong_reference_search)
        self.assertTrue(a.fit(raw,fn)['accepted']);self.assertTrue(b.fit(raw,fn)['accepted'])
        self.assertEqual([a.decide(x) for x in range(-16,17)], [b.decide(x) for x in range(-16,17)])

    def test_nonlinearity_not_certified_by_affine_proposal(self):
        fn=lambda x:x*x-9
        p=self.law(0,5,fn(0),fn(5))
        self.assertNotEqual(fn(p),0)

    def test_unknown_branch_retained(self):
        q=Queen(self.builders[1],self.law)
        raw=lambda x:x*x
        hidden=lambda x:3*x*(x-1)+2*x+5+int(x==13)
        self.assertTrue(q.fit(raw,hidden)['accepted'])
        self.assertNotEqual(q.decide(13),hidden(13))


if __name__=='__main__':unittest.main()
