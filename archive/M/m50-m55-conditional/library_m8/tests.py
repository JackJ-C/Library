"""M8–M11 新增测试。负例是研究者构造，不冒充系统自主发现。"""
import unittest
from dataclasses import FrozenInstanceError
from itertools import product
from .core import (Ledger, PolynomialReader, World, acceptable, bits, features,
                   majority_error, monomials, repetitions, solve)
from .study import true_degree, table_from_coefficients


class CoreTests(unittest.TestCase):
    def test_solver_matches_small_brute_force(self):
        equations = [(a, b) for a in range(8) for b in (0, 1)]
        for rows in product(equations, repeat=3):
            expected = [c for c in range(8) if all((bits(a & c) & 1) == b for a, b in rows)]
            actual = solve(rows)
            self.assertEqual(actual is None, not expected)
            if actual is not None:
                self.assertIn(actual[0], expected)

    def test_solver_rejects_bad_equation(self):
        with self.assertRaises(ValueError):
            solve([(1, 2)])

    def test_basis_counts(self):
        self.assertEqual([len(monomials(3, k)) for k in range(4)], [1, 4, 7, 8])
        self.assertEqual(len(monomials(4, 2)), 11)

    def test_full_basis_is_invertible(self):
        for d in (1, 2, 3, 4):
            terms = monomials(d, d)
            self.assertEqual(solve((features(x, terms), 0) for x in range(1 << d))[1], 1 << d)

    def test_cubic_counterexample_expands(self):
        reader = PolynomialReader(3)
        for x in sorted(range(8), key=lambda x: (bits(x), x)):
            reader.observe(x, int(x == 7))
        self.assertEqual(reader.degree, 3)
        self.assertEqual(reader.table(), 128)
        self.assertEqual(len(reader.expansions), 2)
        self.assertTrue(reader.certify_full_universe())

    def test_fixed_affine_rejects_cubic(self):
        reader = PolynomialReader(3, maximum=1)
        for x in sorted(range(8), key=lambda x: (bits(x), x)):
            reader.observe(x, int(x == 7))
        self.assertTrue(reader.failed)
        self.assertFalse(reader.certify_full_universe())
        with self.assertRaises(ValueError):
            reader.table()

    def test_partial_fit_is_not_full_certificate(self):
        reader = PolynomialReader(3)
        for x in (0, 1, 2, 4):
            reader.observe(x, 0)
        self.assertEqual(reader.rank, 4)
        self.assertFalse(reader.certify_full_universe())

    def test_duplicate_does_not_double_evidence(self):
        reader = PolynomialReader(3)
        reader.observe(0, 0)
        count = len(reader.ledger.records)
        reader.observe(0, 0)
        self.assertEqual(len(reader.ledger.records), count)
        with self.assertRaises(ValueError):
            reader.observe(0, 1)

    def test_model_predictions_reject_outside_scope(self):
        reader = PolynomialReader(3)
        with self.assertRaises(ValueError):
            reader.predict(8)

    def test_environment_cancelled_exhaustively(self):
        for f, e, b in product((0, 1), repeat=3):
            world = World(1, f, e)
            self.assertEqual(world.observe(0, b) ^ world.observe(0, b, True), f)

    def test_actual_deployment_changes_output(self):
        world = World(3, 128, 127)
        self.assertEqual(world.execute(7, 0), 1)
        world.correction = lambda x: int(x == 7)
        self.assertEqual(world.execute(7, 0), 0)

    def test_independent_degree_evaluator(self):
        for degree in (1, 2, 3):
            for c in range(1 << len(monomials(3, degree))):
                self.assertLessEqual(true_degree(table_from_coefficients(c, 3, degree), 3), degree)


class EvidenceTests(unittest.TestCase):
    def test_missing_source_rejected(self):
        with self.assertRaises(ValueError):
            Ledger().add("observation", "", {})

    def test_future_and_self_reference_rejected(self):
        for parent in (0, 1, -1):
            with self.assertRaises(ValueError):
                Ledger().add("claim", "Queen", {}, refs=(parent,))

    def test_record_is_frozen_and_body_copied(self):
        ledger, body = Ledger(), {"x": [1]}
        ledger.add("observation", "Worker", body)
        body["x"].append(2)
        self.assertEqual(ledger.records[0].body, '{"x":[1]}\n')
        with self.assertRaises(FrozenInstanceError):
            ledger.records[0].source = "Queen"

    def test_reference_not_dependency(self):
        ledger = Ledger()
        a = ledger.add("assumption", "Queen", {})
        c = ledger.add("claim", "Queen", {}, deps=(a,))
        r = ledger.add("review", "Queen", {"claim_wrong": True}, refs=(c,))
        ledger.revoke(a, "model changed")
        self.assertIn(c, ledger.invalid)
        self.assertNotIn(r, ledger.invalid)
        self.assertEqual(ledger.invalid, ledger.recompute())

    def test_reading_does_not_relabel_actor(self):
        ledger = Ledger()
        w = ledger.add("observation", "Worker", {})
        ledger.add("review", "Queen", {}, refs=(w,))
        self.assertEqual(ledger.records[w].source, "Worker")

    def test_invalid_dependency_rejected(self):
        ledger = Ledger()
        a = ledger.add("assumption", "Queen", {})
        ledger.revoke(a, "changed")
        with self.assertRaises(ValueError):
            ledger.add("claim", "Queen", {}, deps=(a,))

    def test_revocation_preserves_historical_record(self):
        ledger = Ledger()
        a = ledger.add("assumption", "Queen", {"degree": 1})
        original = ledger.records[a]
        ledger.revoke(a, "changed")
        self.assertEqual(ledger.records[a], original)
        self.assertEqual(len(ledger.records), 2)

    def test_empty_candidates_do_not_authorize(self):
        self.assertEqual(acceptable([], {}), set())

    def test_expansion_can_revoke_all_permissions(self):
        allowed = {0: {0}, 1: {1}}
        self.assertEqual(acceptable([0], allowed), {0})
        self.assertEqual(acceptable([0, 1], allowed), set())

    def test_pairwise_overlap_insufficient(self):
        allowed = {0: {0, 1}, 1: {1, 2}, 2: {0, 2}}
        self.assertEqual(acceptable([0, 1, 2], allowed), set())


class RiskTests(unittest.TestCase):
    def test_exact_majority_probability(self):
        self.assertAlmostEqual(majority_error(3, 0.1), 0.028)
        self.assertAlmostEqual(majority_error(1, 0.1), 0.1)

    def test_invalid_risk_assumptions_rejected(self):
        for n, p in ((0, 0.1), (2, 0.1), (3, 0.5), (3, -0.1)):
            with self.assertRaises(ValueError):
                majority_error(n, p)

    def test_risk_budget_is_prespecified(self):
        for t in range(1, 9):
            delta = 0.05 / (t * (t + 1))
            n = repetitions(8, 0.1, delta)
            self.assertLessEqual(8 * majority_error(n, 0.1), delta)
            if n > 1:
                self.assertGreater(8 * majority_error(n - 2, 0.1), delta)

    def test_unobserved_change_is_indistinguishable(self):
        old, new = World(3, 0), World(3, 128)
        self.assertEqual([old.paired(x) for x in (0, 1, 2, 4)],
                         [new.paired(x) for x in (0, 1, 2, 4)])
        self.assertNotEqual(old.paired(7), new.paired(7))

    def test_changing_environment_breaks_cancellation(self):
        # 配对中环境发生变化：f=0，完整观测环境=0，旁路观测环境=1。
        paired = World(1, 0, 0).observe(0) ^ World(1, 0, 1).observe(0, bypass=True)
        self.assertNotEqual(paired, 0)

    def test_correlated_errors_not_removed_by_repetition(self):
        repeated = [1] * 11
        self.assertEqual(int(sum(repeated) > len(repeated) // 2), 1)
        self.assertLess(8 * majority_error(11, 0.1), 0.1)


if __name__ == "__main__":
    unittest.main()
