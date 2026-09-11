"""回归、反例与穷举的独立入口。"""
import unittest
from .engine import Model, World, Trace, Probe, QUERIES, episode, repair, parity, validate, Controller, Genome


class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = Model()

    def test_world_model_all_32768_measurements(self):
        for h in range(256):
            world = World(h)
            for q, probe in enumerate(QUERIES):
                predicted = (self.m.ones[q] >> h) & 1
                for payload in (0, 1):
                    for correction in range(4):
                        self.assertEqual(world.step(probe, correction, payload),
                                         predicted ^ payload ^ parity(correction & probe.context))

    def test_trace_snapshot(self):
        t, body = Trace(), {"x": [1]}
        i = t.append("action", "worker/v0", "A", body)
        body["x"].append(2)
        t.export()[0]["body"]["x"].append(3)
        self.assertEqual(t.read(i, i)["body"], {"x": [1]})

    def test_future_and_refs(self):
        t = Trace()
        t.append("action", "worker", "A", {})
        i = t.append("review", "queen", "A", {}, (0,))
        with self.assertRaises(ValueError):
            t.read(i, 0)
        with self.assertRaises(ValueError):
            t.append("review", "queen", "A", {}, (2,))

    def test_scope_preserved(self):
        t = Trace()
        t.append("observation", "worker-A", "A", {})
        t.append("observation", "worker-B", "B", {})
        self.assertEqual(len(t.evidence("A", 1)), 1)
        self.assertEqual(t.evidence("A", 1)[0]["source"], "worker-A")

    def test_replay_idempotent(self):
        s = self.m.update(self.m.all, 7, 1)
        self.assertEqual(self.m.update(s, 7, 1), s)
        self.assertEqual(self.m.update(s, 7, 0), 0)
        self.assertEqual(self.m.options(0), ())
        self.assertIsNone(self.m.choose(0))

    def test_target_identification_not_identity(self):
        for h in range(256):
            run = episode(self.m, World(h).step)
            self.assertTrue((run["state"] >> h) & 1)
            self.assertEqual(run["repair"], repair(h))
            self.assertEqual(run["state"].bit_count(), 16)
            self.assertEqual(len(run["queries"]), 4)

    def test_flat_equivalence(self):
        for h in range(256):
            a = episode(self.m, World(h).step)
            b = episode(self.m, World(h).step, "flat")
            self.assertEqual(a, b)

    def test_transition_all_changed_values(self):
        for h in range(256):
            state = episode(self.m, World(h).step)["state"]
            for j in range(4):
                new = self.m.transition(state, (j,))
                for delta in range(4):
                    self.assertTrue((new >> (h ^ (delta << (2 * j)))) & 1)

    def test_known_correction_normalized(self):
        for h in (0, 3, 17, 85, 255):
            for old in range(4):
                a = episode(self.m, World(h).step, correction=old)
                self.assertEqual(a["repair"], repair(h))

    def test_gate_checks_all_tasks(self):
        for h in range(256):
            for candidate in range(4):
                result = validate(World(h).step, 0, candidate)
                self.assertEqual(result["accepted"], candidate == repair(h))
                self.assertEqual(len(result["rows"]), 8)

    def test_nonlinear_blindspot_rejected(self):
        for h in range(256):
            w = World(h, nonlinear=True)
            a = episode(self.m, w.step)
            self.assertIsNotNone(a["repair"])
            self.assertFalse(validate(w.step, 0, a["repair"])["accepted"])

    def test_no_candidate_abstains(self):
        self.assertEqual(validate(World(0).step, 0, None)["status"], "abstain")

    def test_review_of_review_is_automatic(self):
        a = episode(self.m, World(1).step)
        rows = a["trace"]
        reviews = [r for r in rows if r["kind"] == "review"]
        self.assertEqual(len(reviews), 4)
        self.assertEqual(len(reviews[1]["refs"]), 2)
        for r in rows:
            self.assertNotIn("hidden", r["body"])
            self.assertNotIn("true_fault", r["body"])
            self.assertTrue(all(i < r["seq"] for i in r["refs"]))

    def test_adoption_persists(self):
        for h in range(256):
            c = Controller(self.m, World(h).step)
            run, gate = c.cycle()
            self.assertTrue(gate["accepted"])
            self.assertEqual(c.genome.correction, repair(h))
            self.assertEqual(c.genome.version, int(repair(h) != 0))
            for x in range(4):
                self.assertEqual(c.act(Probe(x, 7), neutral=True), 0)
            old = c.genome
            c.cycle()
            self.assertEqual(c.genome, old)

    def test_rejection_retains_genome(self):
        c = Controller(self.m, World(1, nonlinear=True).step)
        old = c.genome
        _, gate = c.cycle()
        self.assertFalse(gate["accepted"])
        self.assertEqual(c.genome, old)
        with self.assertRaises(ValueError):
            Genome(4)

    def test_invalid_inputs(self):
        for x in (-1, 4, True):
            with self.assertRaises(ValueError):
                Probe(x, 0)
        with self.assertRaises(ValueError):
            World(256)
        with self.assertRaises(ValueError):
            World(0).step(Probe(1, 7), correction=4)


if __name__ == "__main__":
    unittest.main()
