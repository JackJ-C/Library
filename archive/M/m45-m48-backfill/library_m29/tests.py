"""Actual execution/negative checks for M29–M31, not a universal autonomy test."""
import unittest
from itertools import islice
from random import Random
from . import learning as L
from .runtime import run_find,run_flatmap,FuelExhausted,SemanticError,tree,digest
from .proof import prove
from .bridge import candidate_factory


class Kernels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        L.SEED_ENABLED=True;cls.discovered=L.bootstrap()
        cls.f=cls.discovered['find']['program'];cls.p=cls.discovered['flatmap']['program']
    def engine(self):return L.GeneratedEngine(self.f,self.p)
    def test_generated_not_preloaded(self):
        self.assertTrue(all(r['attempts']>1 and len(r['rounds'])>1 for r in self.discovered.values()))
    def test_empty_search(self):self.assertIsNone(run_find(self.f,[],lambda x:True)[0])
    def test_first_hit(self):self.assertEqual(run_find(self.f,range(10),lambda x:x>4)[0],5)
    def test_exhausted(self):self.assertIsNone(run_find(self.f,range(10),lambda x:False)[0])
    def test_long_tail_does_not_overflow(self):self.assertEqual(run_find(self.f,range(5000),lambda x:x==4999)[0],4999)
    def test_flatmap_order_and_duplicates(self):self.assertEqual(run_flatmap(self.p,[2,1,2],lambda x:(x,x))[0],(2,2,1,1,2,2))
    def test_flatmap_empty(self):self.assertEqual(run_flatmap(self.p,[],lambda x:(x,))[0],())
    def test_flatmap_empty_expansions(self):self.assertEqual(run_flatmap(self.p,[1,2],lambda x:())[0],())
    def test_fuel_is_enforced(self):
        with self.assertRaises(FuelExhausted):run_find(self.f,range(30),lambda x:False,2)
    def test_bad_grammar_rejected(self):
        with self.assertRaises(SemanticError):run_find(('eval_python',),[],lambda x:True)
    def test_unprotected_head_rejected(self):
        with self.assertRaises(SemanticError):run_find(('here',),[],lambda x:True)
    def test_induction_find(self):self.assertTrue(prove(self.f,'find')['passed'])
    def test_induction_flatmap(self):self.assertTrue(prove(self.p,'flatmap')['passed'])
    def test_bad_proof_rejected(self):self.assertFalse(prove(('none',),'find')['passed'])
    def test_reverse_concat_rejected(self):
        p=('empty',('nil',),('join',('recur',),('mapped',)))
        self.assertFalse(prove(p,'flatmap')['passed'])
    def test_mutable_kernel_invalidates_certificate(self):
        e=self.engine();e.finder=('none',);self.assertFalse(e.valid())
        with self.assertRaises(SemanticError):e.first([1],lambda x:True)
    def test_bad_kernel_cannot_be_installed(self):
        with self.assertRaises(SemanticError):L.GeneratedEngine(('none',),self.p)
    def test_generated_candidate_sequence_matches_seed(self):
        e=self.engine()
        for kind in ('find','flatmap'):
            self.assertEqual(list(L.seed_candidates(kind,5)),list(e.candidates(kind,5)))
    def test_disabled_seed_raises(self):
        L.SEED_ENABLED=False
        try:
            with self.assertRaises(RuntimeError):next(L.seed_candidates('find'))
            with self.assertRaises(RuntimeError):L.discover('find')
        finally:L.SEED_ENABLED=True
    def test_generated_handoff_with_seed_disabled(self):
        L.SEED_ENABLED=False
        try:self.assertEqual(L.discover('find',self.engine())['program'],self.f)
        finally:L.SEED_ENABLED=True
    def test_new_length_challenges(self):
        for k,p in [('find',self.f),('flatmap',self.p)]:
            self.assertTrue(all(r['failure'] is None for r in L.challenge(p,k)))
    def test_m25_bank_sequence_equal(self):
        from library_m25.language import candidate_factory as baseline
        for names in [('a','b'),('p0','p1','r0','r1')]:
            self.assertEqual(list(islice(candidate_factory(self.engine(),names,True)(),2000)),
                             list(islice(baseline(names,True)(),2000)))
    def test_no_index_lookup(self):
        xs=list(range(99));Random(24).shuffle(xs)
        self.assertEqual(self.engine().first(xs,lambda x:x==73),73)
    def test_generated_origin_not_all_origins(self):
        from .study import origins
        self.assertFalse(origins()['all_high_level_rules_autonomously_originated'])
    def test_bad_predicate_cannot_be_self_certified(self):
        self.assertEqual(self.engine().first(range(4),lambda x:True),0)
        self.assertNotEqual(self.engine().first(range(4),lambda x:True),3)
    def test_prior_counterexamples_retained(self):
        for r in self.discovered.values():
            seen=set()
            for row in r['rounds']:
                self.assertLessEqual(seen,set(row['active_before']))
                if row['counterexample']:seen.add(row['counterexample']['id'])


class ExecutionGuardTests(unittest.TestCase):
    def test_new_guard_denies_unapproved_execution(self):
        from .bridge import GatedQueen
        q=GatedQueen(lambda f:f,lambda *args:0)
        with self.assertRaises(RuntimeError):q.decide(1)

    def test_legacy_class_is_not_silently_replaced(self):
        from .bridge import GatedQueen
        from library_m25.experiments import Queen
        self.assertIsNot(Queen,GatedQueen)
        self.assertEqual(Queen(lambda f:f,lambda *args:0).decide(1),0)


if __name__=='__main__':unittest.main()
