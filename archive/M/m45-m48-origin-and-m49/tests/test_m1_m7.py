"""有限契约、反例与实现交叉核对。不是自然任务上的泛化测试。"""
from dataclasses import FrozenInstanceError, replace
import inspect
import unittest
from library_experiments import *


class ExperimentTests(unittest.TestCase):
    def test_independent_world_model_all_queries(self):
        for h in PARAMS:
            w = World(h)
            for q in range(16):
                self.assertEqual(w.observe(q), prediction(h, q))

    def test_four_correct_repair_classes(self):
        self.assertEqual([m.bit_count() for m in CLASSES], [64]*4)
        self.assertEqual(sum(CLASSES), ALL)

    def test_active_all_worlds(self):
        for i, h in enumerate(PARAMS):
            d = diagnose(World(h).observe)
            self.assertEqual(d['choices'], [repair(h)])
            self.assertEqual(d['cost']['interactions'], 4)
            self.assertTrue(d['H'] & (1 << i))
            self.assertEqual(d['H'].bit_count(), 16)

    def test_full_identification_all_worlds(self):
        for i, h in enumerate(PARAMS):
            d = diagnose(World(h).observe, purpose='identify')
            self.assertEqual(ids(d['H']), [i])
            self.assertEqual(d['cost']['interactions'], 8)

    def test_passive_abstains(self):
        for h in PARAMS:
            d = diagnose(World(h).observe, policy='passive')
            self.assertEqual(d['status'], 'unresolved')
            self.assertEqual(len(d['choices']), 4)

    def test_plain_log_exact_equivalence(self):
        for h in PARAMS:
            a = diagnose(World(h).observe, trace=True)
            b = diagnose(World(h).observe, trace=True, backend='plain')
            self.assertEqual(a, b)

    def test_random_is_reproducible_and_bounded(self):
        for seed in range(64):
            a = diagnose(World(PARAMS[109]).observe, policy='random', seed=seed)
            b = diagnose(World(PARAMS[109]).observe, policy='random', seed=seed)
            self.assertEqual(a, b)
            self.assertLessEqual(a['cost']['interactions'], 16)
            self.assertEqual(len(a['history']), len(set(q for q,y in a['history'])))

    def test_observer_revisits_own_review(self):
        d = diagnose(World(PARAMS[109]).observe, trace=True)
        reviews = [r for r in d['records'] if r['kind'] == 'review']
        self.assertEqual(len(reviews), 4)
        self.assertIn(reviews[0]['key'], reviews[1]['refs'])
        self.assertTrue(any(json.loads(r['body'])['revised'] for r in reviews))
        self.assertTrue(all(r['source'] == 'queen' for r in reviews))

    def test_no_hidden_parameters_in_diagnoser(self):
        source = inspect.getsource(diagnose)
        self.assertNotIn('_theta', source)
        self.assertNotIn('__self__', source)

    def test_bad_source_rejected(self):
        l = Ledger()
        k = l.append('rig','v0','feedback',{'q':0,'y':0})
        r = l.read(k,k)
        with self.assertRaises(ValueError):
            feedback(replace(r, source='queen'), 'v0')

    def test_wrong_version_rejected(self):
        l = Ledger()
        k = l.append('rig','v0','feedback',{'q':0,'y':0})
        with self.assertRaises(ValueError):
            feedback(l.read(k,k), 'v1')

    def test_future_evidence_rejected(self):
        l = Ledger()
        k = l.append('rig','v0','feedback',{'q':0,'y':0})
        with self.assertRaises(ValueError):
            l.read(k,k-1)

    def test_future_reference_rejected(self):
        with self.assertRaises(ValueError):
            Ledger().append('queen','v0','review',{},(1,))

    def test_record_is_frozen_snapshot(self):
        l, obj = Ledger(), {'a':[1]}
        k = l.append('queen','v0','review',obj)
        obj['a'].append(2)
        self.assertEqual(json.loads(l.read(k,k).body), {'a':[1]})
        with self.assertRaises(FrozenInstanceError):
            l.read(k,k).body = '{}'

    def test_inconsistent_evidence_empty(self):
        self.assertEqual(filter_H(filter_H(ALL,0,0),0,1),0)
        self.assertFalse(resolved(0,'repair'))
        with self.assertRaises(ValueError):
            common_safe(0)

    def test_invalid_inputs(self):
        for y in (True,2,None,'1'):
            with self.assertRaises(ValueError):
                filter_H(ALL,0,y)
        with self.assertRaises(ValueError):
            World((0,0,0,0)).apply(4)

    def test_real_adoption_and_noop(self):
        for h in PARAMS:
            w = World(h)
            a = adopt(w,diagnose(w.observe)['choices'][0])
            self.assertTrue(a['accepted'])
            self.assertTrue(all(a['challenge']))
            self.assertEqual(a['regressions'],0)

    def test_outside_family_is_counterexample(self):
        w = World((1,0,0,0),nonlinear=True)
        a = adopt(w,diagnose(w.observe)['choices'][0])
        self.assertTrue(a['accepted'])
        self.assertFalse(all(a['challenge']))

    def test_failed_validation_rolls_back(self):
        w = World((1,0,0,0),payload_fault=True)
        a = adopt(w,diagnose(w.observe)['choices'][0])
        self.assertFalse(a['accepted'])
        self.assertEqual(w.correction,0)

    def test_lift_preserves_truth_for_all_single_changes(self):
        for i,h in enumerate(PARAMS):
            for j in range(4):
                H = lift(1<<i,(j,))
                self.assertEqual(H.bit_count(),4)
                for value in range(4):
                    new = list(h); new[j] = value
                    self.assertTrue(H & (1<<PARAMS.index(tuple(new))))

    def test_empty_scope_retains_all_scope_forgets(self):
        self.assertEqual(lift(1<<109,()),1<<109)
        self.assertEqual(lift(1<<109,tuple(range(4))),ALL)

    def test_external_cancellation_counterexample(self):
        w = World((1,0,0,1))
        self.assertTrue(all(w.execute(x,b)==b for x,b in CASES))
        d = diagnose(w.observe)
        self.assertEqual(common_safe(d['H']),[])
        w.apply(d['choices'][0])
        self.assertTrue(all(w.execute(x,b,neutral=True)==b for x,b in CASES))
        self.assertFalse(all(w.execute(x,b)==b for x,b in CASES))

    def test_certificate_matches_independent_simulator(self):
        for h in PARAMS:
            d = diagnose(World(h).observe)
            good = []
            for u in range(4):
                old,new = World(h),World(h); new.apply(u)
                if all(new.execute(x,b,neutral=True)==b for x,b in CASES) and all(old.execute(x,b)!=b or new.execute(x,b)==b for x,b in CASES):
                    good.append(u)
            self.assertEqual(common_safe(d['H']),good)


if __name__ == '__main__':
    unittest.main()
