"""手工构造的正反例；不代表系统自主发现不足。"""
from dataclasses import FrozenInstanceError, replace
import unittest
from library_m0.core import Actor, ContractError, Judgment, Library, evidence_digest, gap, square


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.w = Actor("worker", "v0")
        self.q = Actor("queen", "v0")
        self.lib = Library()
        self.first = self.lib.append("s0", self.w, 0, 0, {"outcome": None})

    def chain(self):
        self.lib.append("s1", self.w, 0, 2, {"outcome": 0}, refs=("s0",))
        self.lib.append("s2", self.q, 3, 3, {"judgment": "unknown cause"},
                        kind="review", refs=("s1",))

    def test_source_is_not_reader(self):
        reading = self.lib.read("s0", 0, self.q)
        self.assertEqual(reading.record.source, self.w)
        self.assertEqual(reading.reader, self.q)
        self.assertNotEqual(reading.reader, reading.record.source)

    def test_same_code_does_not_merge_instances(self):
        clone = Actor("worker-clone", "v0")
        self.assertNotEqual(clone, self.w)
        self.assertEqual(self.lib.read("s0", 0, clone).record.source, self.w)

    def test_nested_payload_is_snapshot(self):
        body = {"data": [1]}
        record = self.lib.append("nested", self.w, 1, 1, body)
        body["data"].append(2)
        record.payload()["data"].append(3)
        self.assertEqual(record.payload(), {"data": [1]})

    def test_slice_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            self.first.kind = "review"

    def test_duplicate_is_rejected(self):
        with self.assertRaises(ContractError):
            self.lib.append("s0", self.w, 1, 1, {})
        self.assertIsNone(self.lib.read("s0", 1, self.q).record.payload()["outcome"])

    def test_unknown_outcome_remains_unknown(self):
        self.assertIsNone(self.first.payload()["outcome"])

    def test_late_evidence_not_visible_in_past(self):
        self.chain()
        with self.assertRaises(ContractError):
            self.lib.read("s1", 1, self.q)
        self.assertEqual(self.lib.read("s1", 2, self.q).record.payload()["outcome"], 0)

    def test_invalid_times_rejected(self):
        for event, available in [(2, 1), (-1, 1), (0, 0), (True, 1), (0, 1.5)]:
            with self.subTest(event=event, available=available):
                with self.assertRaises(ContractError):
                    self.lib.append("bad", self.w, event, available, {})

    def test_invalid_metadata_rejected(self):
        for kwargs in ({"kind": "truth"}, {"refs": ["s0"]},
                       {"refs": ("s0", "s0")}, {"kind": "review"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ContractError):
                    self.lib.append("bad", self.w, 1, 1, {}, **kwargs)

    def test_future_and_self_references_rejected(self):
        for ref in ("future", "new"):
            with self.assertRaises(ContractError):
                self.lib.append("new", self.w, 1, 1, {}, refs=(ref,))

    def test_nan_and_non_json_rejected(self):
        for value in (float("nan"), float("inf"), object()):
            with self.assertRaises(ContractError):
                self.lib.append("bad", self.w, 1, 1, {"x": value})
        # 失败不能消耗逻辑时刻或污染存储。
        self.lib.append("valid", self.w, 1, 1, {})

    def test_unknown_key_rejected(self):
        with self.assertRaises(ContractError):
            self.lib.read("absent", 0, self.q)

    def test_review_of_review_retains_sources(self):
        self.chain()
        self.lib.append("s3", Actor("queen", "v1"), 4, 4,
                        {"missing_probe": "hold environment fixed"},
                        kind="review", refs=("s2",))
        path = self.lib.traverse("s3", 4, self.q)
        self.assertEqual(path.keys, ("s3", "s2", "s1", "s0"))
        self.assertFalse(path.truncated)
        self.assertEqual(self.lib.read("s1", 4, self.q).record.source, self.w)

    def test_depth_budget_reports_truncation(self):
        self.chain()
        result = self.lib.traverse("s2", 3, self.q, max_depth=0)
        self.assertEqual(result.keys, ("s2",))
        self.assertTrue(result.truncated)

    def test_node_budget_reports_truncation(self):
        self.chain()
        result = self.lib.traverse("s2", 3, self.q, max_nodes=2)
        self.assertEqual(result.keys, ("s2", "s1"))
        self.assertTrue(result.truncated)

    def test_byte_budget_reports_truncation(self):
        result = self.lib.traverse("s0", 0, self.q, max_bytes=1)
        self.assertEqual(result.keys, ())
        self.assertEqual(result.bytes_read, 0)
        self.assertTrue(result.truncated)

    def test_exact_byte_budget_succeeds(self):
        size = len(self.first.serial().encode("utf-8"))
        result = self.lib.traverse("s0", 0, self.q, max_bytes=size)
        self.assertEqual(result.bytes_read, size)
        self.assertFalse(result.truncated)

    def test_invalid_budgets_rejected(self):
        for kwargs in ({"max_nodes": 0}, {"max_depth": -1}, {"max_bytes": 0},
                       {"max_nodes": True}):
            with self.assertRaises(ContractError):
                self.lib.traverse("s0", 0, self.q, **kwargs)

    def test_shared_ancestor_not_duplicated(self):
        self.lib.append("b", self.q, 1, 1, {}, refs=("s0",))
        self.lib.append("c", self.q, 2, 2, {}, refs=("s0",))
        self.lib.append("d", self.q, 3, 3, {}, refs=("b", "c"))
        result = self.lib.traverse("d", 3, self.q)
        self.assertEqual(result.keys, ("d", "b", "c", "s0"))
        self.assertFalse(result.truncated)

    def test_digest_tracks_contents_and_order(self):
        self.chain()
        second = self.lib.read("s1", 3, self.q).record
        self.assertNotEqual(evidence_digest((self.first, second)),
                            evidence_digest((second, self.first)))
        self.assertEqual(evidence_digest((self.first,)), evidence_digest((self.first,)))


class JudgmentTests(unittest.TestCase):
    def setUp(self):
        self.j = Judgment(Actor("queen", "v0"), "success?", "worker/v0", "digest", 1, 0)

    def test_frozen_reobservation_has_zero_gap(self):
        self.assertEqual(gap(self.j, self.j), {"status": "comparable", "gap": 0})

    def test_changed_reader_can_be_compared(self):
        other = replace(self.j, reader=Actor("queen", "v1"), value=1)
        self.assertEqual(gap(self.j, other)["gap"], 1)

    def test_uncontrolled_comparisons_rejected(self):
        for field, value in (("question", "other?"), ("target", "clone"),
                             ("evidence", "future"), ("horizon", 2), ("random_key", "new")):
            with self.subTest(field=field):
                self.assertEqual(gap(self.j, replace(self.j, **{field: value})),
                                 {"status": "not_comparable", "gap": None})

    def test_unknown_judgment_is_not_zero(self):
        self.assertEqual(gap(self.j, replace(self.j, value=None)),
                         {"status": "unknown", "gap": None})

    def test_invalid_judgment_rejected(self):
        for value in (float("nan"), float("inf"), True, "1"):
            with self.assertRaises(ContractError):
                replace(self.j, value=value)

    def test_square_preserves_interaction(self):
        result = square(0, 0, 0, 1)
        self.assertEqual(result, {"reader": 0, "evidence": 0, "interaction": 1, "total": 1})
        with self.assertRaises(ContractError):
            square(0, 0, 0, None)


if __name__ == "__main__":
    unittest.main()
