"""Post-freeze audit regression tests and an ordering counterexample, not RSI trials."""
import copy
import json
import lzma
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_r31 import audit_episode, finite
from r28_r31.verify import verify_episode
from r28_r31.tests import small_space, response


def order_counterexample():
    columns = [[response(0), response(0), response(1)],
               [response(0), response(1), response(1)],
               [response(0), response(1), response(2)]]
    _, a, _ = small_space(columns)
    _, b, _ = small_space([columns[2], columns[0], columns[1]])
    return {'first_order': ['A','B','C'], 'second_order': ['C','A','B'],
            'first_axes': a.axes, 'second_axes': b.axes,
            'first_classes': a.groups, 'second_classes': b.groups,
            'first_distances': a.matrix()[1], 'second_distances': b.matrix()[1],
            'same_equivalence': a.groups == b.groups,
            'different_distance': a.matrix()[1] != b.matrix()[1],
            'interpretation': 'Greedy witness selection depends on acquisition order; not intrinsic geometry.'}


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x = json.loads(lzma.decompress((ROOT/'results/r28_r31/A/43100_space.json.xz').read_bytes()))

    def rejects(self, change):
        x = copy.deepcopy(self.x); change(x)
        with self.assertRaises(ValueError): audit_episode(x, run_arithmetic=False)

    def test_unmodified_archive(self):
        self.assertTrue(audit_episode(self.x, run_arithmetic=False)['passed'])

    def test_old_verifier_misses_summary_tamper(self):
        x=copy.deepcopy(self.x); x['summary']['updates']=999
        self.assertTrue(verify_episode(x)['passed'])
        with self.assertRaises(ValueError): audit_episode(x, run_arithmetic=False)

    def test_averages_linked_to_blocks(self):
        self.rejects(lambda x: x['rounds'][0]['evaluation_only']['means'].__setitem__('child', .9))

    def test_causal_difference_linked(self):
        self.rejects(lambda x: x['rounds'][0].__setitem__('delta', .5))

    def test_actual_prior_adoption_linked(self):
        self.rejects(lambda x: x['rounds'][1].__setitem__('previous_adopted', True))

    def test_adoption_values_linked_to_cells(self):
        def mutate(x):
            i=x['rounds'][0]['check_record']; b=json.loads(x['ledger'][i]['body'])
            b['checks']['primary']['old'][0] += .1
            x['ledger'][i]['body']=json.dumps(b)
        self.rejects(mutate)

    def test_ranking_recomputed(self):
        def mutate(x):
            i=x['rounds'][0]['proposal_record']; b=json.loads(x['ledger'][i]['body'])
            b['branches']['primary']['selection']['ranking'][0]['priorities'][0][1] += .1
            x['ledger'][i]['body']=json.dumps(b)
        self.rejects(mutate)

    def test_coordinate_support_not_cosmetic(self):
        def mutate(x):
            i=x['rounds'][0]['space']['coordinate_records'][0]
            x['ledger'][i]['deps']=[]
        self.rejects(mutate)

    def test_actual_bundle_binding_linked(self):
        def mutate(x):
            i=x['rounds'][0]['check_record']+1; b=json.loads(x['ledger'][i]['body'])
            b['bundle']['scale']=.5
            x['ledger'][i]['body']=json.dumps(b)
        self.rejects(mutate)

    def test_simulation_cost_linked(self):
        self.rejects(lambda x: x['rounds'][0]['proposal_cost'].__setitem__('simulated_query_price', 1))

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): finite({'x': float('inf')})
        with self.assertRaises(ValueError): finite({'x': float('nan')})

    def test_witness_order_counterexample(self):
        r=order_counterexample()
        self.assertTrue(r['same_equivalence'] and r['different_distance'])
        self.assertEqual(r['first_distances'][0][1], .5)
        self.assertEqual(r['second_distances'][0][1], 1.)


if __name__=='__main__':
    (ROOT/'results/r28_r31/ORDER_COUNTEREXAMPLE.json').write_text(
        json.dumps(order_counterexample(),ensure_ascii=False,indent=2)+'\n')
    unittest.main(verbosity=2)
