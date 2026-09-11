"""本阶段正反例；通过反例测试不表示对应压力条件下修复成功。"""
from dataclasses import FrozenInstanceError, replace
import unittest
from .synthesis import synthesize, compile_expr, evaluate, source
from .recovery import Cell, SLOTS, Context, Ballot, quorum, recover, probe, audit
from .study import group, learn, history_comparison, INITIAL, VALIDATION, FUTURE


class SynthesisTests(unittest.TestCase):
    def test_generated_callable_matches_independent_interpreter(self):
        expressions = [
            ('mul', ('x',), ('abs', ('x',))),
            ('add', ('parity', ('x',)), ('mul', ('c', -2), ('x',))),
            ('half', ('sub', ('x',), ('c', 3))),
            ('abs', ('sub', ('x',), ('c', 2)))]
        for e in expressions:
            fn = compile_expr(e)
            for x in range(-32, 33):
                self.assertEqual(fn(x), evaluate(e, x))

    def test_unknown_operator_rejected(self):
        with self.assertRaises(ValueError): source(('import', ('x',)))

    def test_no_arbitrary_source_constant(self):
        with self.assertRaises(ValueError): compile_expr(('c', '__import__'))

    def test_actual_nonlinear_program_generated(self):
        answer = synthesize(tuple((x, x*x) for x in INITIAL))
        self.assertEqual(answer['status'], 'fit')
        fn = compile_expr(answer['candidate'].expression)
        self.assertEqual(fn(19), 361)

    def test_inconsistent_observations_reported(self):
        self.assertEqual(synthesize(((1, 2), (1, 3)))['status'], 'inconsistent')

    def test_resource_exhaustion_is_not_success(self):
        result = synthesize(tuple((x, x*x) for x in INITIAL), max_nodes=1, budget=7)
        self.assertIsNone(result['candidate'])
        self.assertEqual(result['status'], 'budget_or_grammar_exhausted')

    def test_real_decide_uses_generated_binding(self):
        c = Cell('same-instance')
        original = id(c)
        record = learn(c, lambda x: abs(x-2))
        self.assertTrue(record['accepted'])
        self.assertEqual(id(c), original)
        self.assertEqual(c.decide(-29), 31)

    def test_holdout_is_disjoint(self):
        self.assertFalse(set(FUTURE) & set(INITIAL + VALIDATION))
        self.assertEqual(len(FUTURE), 56)

    def test_history_and_remeasurement_match_without_holdout_queries(self):
        seen = []
        def oracle(x):
            seen.append(x)
            return x*x
        old = tuple((x, x*x) for x in INITIAL)
        r = history_comparison(old, oracle)
        self.assertEqual(seen, list(INITIAL))
        self.assertTrue(r['same_program'])
        self.assertEqual(r['history_additional_calls'], 0)
        self.assertEqual(r['remeasure_additional_calls'], 5)
        self.assertEqual(r['no_history_no_probe'], 'insufficient_evidence')

    def test_all_learning_interactions_are_recorded(self):
        seen = []
        def oracle(x):
            seen.append(x)
            return x*x
        report = learn(Cell('counted'), oracle)
        self.assertEqual(report['oracle_calls'], len(seen))
        self.assertEqual([x for x, _ in report['query_trace']], seen)
        self.assertFalse(set(seen) & set(FUTURE))

    def test_future_trigger_not_ruled_out_by_seen_points(self):
        c = Cell('latent')
        f = lambda x: x*x + int(x == 17)
        r = learn(c, f)
        self.assertTrue(r['accepted'])
        self.assertNotEqual(c.decide(17), f(17))


class RecoveryTests(unittest.TestCase):
    def test_normal_system_untouched(self):
        cells = group()
        fns = [dict(c.functions) for c in cells]
        r = recover(cells)
        self.assertEqual(r['changes'], [])
        for c, old in zip(cells, fns):
            for s in SLOTS: self.assertIs(c.functions[s], old[s])

    def test_no_privileged_immune_cell(self):
        for target in range(4):
            for mode in ('silent', 'exception'):
                cs = group(); ident = id(cs[target]); cs[target].fault(63, mode)
                r = recover(cs)
                self.assertEqual(len(r['changes']), 6)
                self.assertEqual(id(cs[target]), ident)
                self.assertTrue(all(all(audit(probe(c)).values()) for c in cs))

    def test_every_individual_slot_is_recovered(self):
        for bit, slot in enumerate(SLOTS):
            cs = group(); cs[1].fault(1 << bit, 'silent')
            r = recover(cs)
            self.assertEqual([v['slot'] for v in r['changes']], [slot])

    def test_auditor_false_health_is_overruled(self):
        cs = group(); cs[0].fault(63, 'silent')
        self.assertTrue(all(cs[0].call('audit', probe(cs[0])).values()))
        r = recover(cs)
        self.assertEqual(len(r['changes']), 6)
        for change in r['changes']:
            self.assertNotIn('cell-0', change['negative_voters'])

    def test_faulted_generator_really_breaks_inference(self):
        c = Cell('c'); c.fault(4, 'silent')
        self.assertIsNone(c.infer(((0, 1), (1, 2)), 0)['candidate'])

    def test_stale_evidence_filter_is_live(self):
        c = Cell('c')
        c.history = [(0, 0, 8)]
        self.assertEqual(c.infer(((0, 1), (1, 2)), 1)['status'], 'fit')
        c.fault(2, 'silent')
        self.assertEqual(c.infer(((0, 1), (1, 2)), 2)['status'], 'inconsistent')

    def test_whole_bundle_update_increments_version_once(self):
        cs = group(); cs[2].fault(63, 'silent')
        recover(cs)
        self.assertEqual([c.version for c in cs], [0, 0, 1, 0])

    def test_everyone_crashed_is_not_repaired(self):
        cs = group()
        for c in cs: c.fault(63, 'exception')
        r = recover(cs)
        self.assertEqual(r['changes'], [])
        self.assertTrue(r['unresolved'])

    def test_correlated_silent_failures_are_retained(self):
        cs = group()
        for c in cs: c.fault(63, 'silent')
        r = recover(cs)
        self.assertEqual(r['changes'], [])
        self.assertFalse(all(all(v.values()) for v in r['behaviour_after'].values()))


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.ctx = Context('a', 1, 'E', 'P', 'audit')
        self.registry = ('a', 'b', 'c', 'd')
        self.votes = (Ballot('b', self.ctx, True), Ballot('c', self.ctx, True))

    def test_two_distinct_fresh_voters(self):
        self.assertEqual(quorum(self.votes, self.ctx, self.registry), ('b', 'c'))

    def test_duplicate_history_not_new_authority(self):
        self.assertEqual(quorum((self.votes[0],)*100, self.ctx, self.registry), ())

    def test_self_vote_does_not_count(self):
        votes = (Ballot('a', self.ctx, True), self.votes[0])
        self.assertEqual(quorum(votes, self.ctx, self.registry), ())

    def test_stale_versions_rejected(self):
        ctx = replace(self.ctx, version=2)
        self.assertEqual(quorum(self.votes, ctx, self.registry), ())

    def test_candidate_and_evidence_and_slot_bound(self):
        for field in ('candidate', 'evidence', 'slot', 'subject'):
            self.assertEqual(quorum(self.votes, replace(self.ctx, **{field:'other'}), self.registry), ())

    def test_equivocation_is_not_selectively_counted(self):
        votes = self.votes + (Ballot('c', self.ctx, False),)
        self.assertEqual(quorum(votes, self.ctx, self.registry), ())

    def test_unregistered_clone_rejected(self):
        votes = (Ballot('clone1', self.ctx, True), Ballot('clone2', self.ctx, True))
        self.assertEqual(quorum(votes, self.ctx, self.registry), ())

    def test_context_record_is_frozen(self):
        with self.assertRaises(FrozenInstanceError): self.ctx.version = 8

    def test_two_bad_voters_break_assumed_bound(self):
        # 两票均为谎言时，协议没有魔法辨认真相。
        self.assertTrue(quorum(self.votes, self.ctx, self.registry))


if __name__ == '__main__': unittest.main()
