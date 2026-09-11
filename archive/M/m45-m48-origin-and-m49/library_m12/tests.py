"""新测试与旧实现反例，测试失败不等于隐藏其记录。"""
import unittest
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
from random import Random
from .core import (PROGRAMS, Decision, Frame, Packet, Reading, Queen, Worker,
                   compile_judge, infer_programs, reference, simulate, fault_mask)
from .study import make_case, materialize, setup, audit_packets, validation_packets, run_one, pressure_study
from .guard import RevocableReader
from library_m8.core import PolynomialReader


class ExecutionTests(unittest.TestCase):
    def test_independent_candidate_interpreter(self):
        for p, seed in product(PROGRAMS, range(16)):
            packet, _ = make_case(seed, novel=bool(seed % 2))
            self.assertEqual(compile_judge(p)(packet), simulate(p, packet))

    def test_reference_agrees_with_independent_generator(self):
        for seed in range(64):
            p, values = make_case(seed, novel=bool(seed % 2))
            for age in (0, 1):
                self.assertEqual(reference(p, age), values[age])

    def test_actual_fault_is_in_live_judge(self):
        packet, truth = make_case(11)
        for p in PROGRAMS:
            q = Queen(compile_judge(p), 0)
            self.assertEqual(q.decide(packet), simulate(p, packet))
        self.assertNotEqual(Queen(compile_judge((1,0,0)),0).decide(packet).value, truth[0])

    def test_compile_rejects_non_grammar(self):
        for p in ((1,2,3), ('target',0,0), (False,0,0)):
            with self.assertRaises(ValueError):
                compile_judge(p)

    def test_queen_self_repair_preserves_worker(self):
        q, w = setup((1,1,2), (1,0), 0, 1)
        before, identity = w.decoder, id(q)
        q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
        self.assertEqual(id(q), identity)
        self.assertEqual(w.decoder, before)
        self.assertEqual(q.revision, 1)

    def test_worker_repair_preserves_queen_binding(self):
        q, w = setup((0,0,0), (-2,5), 0, 1)
        before = q._judge
        q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
        self.assertIs(q._judge, before)
        self.assertEqual(q.revision, 0)
        self.assertEqual(w.emit(F(12345)), F(12345))

    def test_healthy_system_not_edited(self):
        q, w = setup((0,1,0), (1,0), 1, 0)
        fn, state = q._judge, w.decoder
        d = q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
        self.assertEqual(d['locus'], 'healthy')
        self.assertEqual(d['patches'], [])
        self.assertIs(q._judge, fn)
        self.assertEqual(w.decoder, state)

    def test_fingerprints_not_used_as_fault_labels(self):
        q, w = setup((1,0,2), (1,0), 0, 0)
        q._judge.fingerprint = compile_judge((0,0,0)).fingerprint
        d = q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
        self.assertEqual(d['locus'], 'self')
        self.assertEqual(d['qmask'], [True,False,True])

    def test_minimal_slot_targeting(self):
        for p in PROGRAMS:
            q, w = setup(p, (1,0), 0, 0)
            d = q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
            slots = [j for j, v in enumerate(fault_mask(p,0)) if v]
            self.assertEqual(d['patches'][0]['slots'] if slots else [], slots)

    def test_joint_fault_requires_two_loci(self):
        r = run_one((1,1,2),(-2,5),0,0)
        self.assertEqual(r['four_corner_correct_of_32'], [0,0,0,32])

    def test_task_contract_is_not_always_latest(self):
        q,w = setup((0,0,0),(1,0),1,0)
        d = q.review(w.probe,w.recalibrate,audit_packets(),validation_packets())
        self.assertEqual(d['qmask'],[False,True,False])

    def test_no_history_requires_self_evidence(self):
        q,w = setup((1,1,2),(1,0),0,0)
        d = q.review(w.probe,w.recalibrate,audit_packets(),validation_packets(),'worker_only',0)
        self.assertEqual(d['status'],'abstain')
        self.assertEqual(q.revision,0)
        self.assertEqual(d['candidates'],12)

    def test_self_probe_can_replace_missing_history(self):
        q,w = setup((1,1,2),(1,0),0,0)
        d = q.review(w.probe,w.recalibrate,audit_packets(),validation_packets(),'worker_only',8)
        self.assertEqual(d['locus'],'self')
        self.assertGreater(d['self_queries'],0)

    def test_plain_log_equal(self):
        a,w = setup((1,0,1),(-1,0),0,1)
        b,v = setup((1,0,1),(-1,0),0,1)
        x=a.review(w.probe,w.recalibrate,audit_packets(),validation_packets())
        y=b.review(v.probe,v.recalibrate,audit_packets(),validation_packets(),'plain')
        self.assertEqual(x,y)

    def test_inconsistent_own_trace_abstains(self):
        q,w = setup((0,0,0),(1,0),0,0)
        f=q.history[0]
        q.history[0]=Frame(f.packet, Decision(F(10**20),f.decision.used))
        d=q.review(w.probe,w.recalibrate,audit_packets(),validation_packets())
        self.assertEqual(d['status'],'abstain')
        self.assertEqual(d['candidates'],0)

    def test_zero_gain_cannot_be_inverted(self):
        q,w = setup((0,0,0),(0,7),0,0)
        d=q.review(w.probe,w.recalibrate,audit_packets(),validation_packets())
        self.assertEqual(d['status'],'abstain')
        self.assertIsNone(d['worker_fault'])

    def test_worker_recalibration_composes(self):
        w=Worker(-2,5)
        w.decoder=(F(3),F(4))
        y=[w.probe(F(x)) for x in (-4,0,9)]
        slope=(y[2]-y[0])/13
        w.recalibrate(slope,y[1])
        for x in (-123,0,48):self.assertEqual(w.emit(F(x)),x)

    def test_failed_worker_validation_rolls_back(self):
        q,w=setup((1,0,0),(-2,5),0,0)
        oldq,oldw=q._judge,w.decoder
        def probe(x):
            return w.probe(x) + (1 if x==37 else 0)
        d=q.review(probe,w.recalibrate,audit_packets(),validation_packets())
        self.assertEqual(d['status'],'validation_reject')
        self.assertIs(q._judge,oldq)
        self.assertEqual(w.decoder,oldw)

    def test_missing_grammar_does_not_become_new_success(self):
        r=pressure_study()
        self.assertEqual(r['latent_queen']['challenge_failures_of_32'],32)
        self.assertEqual(r['nonlinear_worker']['status'],'abstain')
        self.assertEqual(r['broken_meta_kernel']['challenge_failures_of_32'],32)

    def test_original_history_is_preserved(self):
        q,w=setup((1,0,0),(1,0),0,0)
        old=tuple(q.history)
        q.review(w.probe,w.recalibrate,audit_packets(),validation_packets())
        self.assertEqual(tuple(q.history[:len(old)]),old)


class CertificateTests(unittest.TestCase):
    def test_original_counterexample_is_reproducible(self):
        r=PolynomialReader(3)
        for x in range(8):r.observe(x,0)
        with self.assertRaises(ValueError):r.observe(0,1)
        # 显式保存旧实现的缺陷，不把它叫作正确行为。
        self.assertTrue(r.certify_full_universe())

    def test_guard_revokes_after_contradiction(self):
        r=RevocableReader(3)
        for x in range(8):r.observe(x,0)
        old=r.last_claim
        with self.assertRaises(ValueError):r.observe(0,1)
        self.assertFalse(r.certify_full_universe())
        self.assertIn(old,r.ledger.invalid)
        self.assertTrue(r.failed)
        with self.assertRaises(ValueError):r.predict(0)

    def test_consistent_duplicate_keeps_certificate(self):
        r=RevocableReader(3)
        for x in range(8):r.observe(x,0)
        r.observe(0,0)
        self.assertTrue(r.certify_full_universe())

    def test_all_full_tables_contradictions(self):
        for table in range(256):
            r=RevocableReader(3)
            for x in range(8):r.observe(x,(table>>x)&1)
            self.assertTrue(r.certify_full_universe())
            with self.assertRaises(ValueError):r.observe(table%8,1-((table>>(table%8))&1))
            self.assertFalse(r.certify_full_universe())


if __name__=='__main__':
    unittest.main()
