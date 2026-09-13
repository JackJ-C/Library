"""Finite mechanism tests; passing them is not an RSI result."""
import copy
import json
import unittest
from collections import Counter
from statistics import mean

from src.core import Queen
from r4_r7 import search
from r20_r23_recovery import racing
from .space import CausalSpace, Response, freeze
from .study import (Bundle, INITIAL, SpaceQueen, InterventionEngine, make_queen,
                    problems, opaque_problems, episode, adoption, choose_proposal)
from .verify import verify_episode, reference_intervention, equal


def response(x, loss=.1):
    return Response(loss, (((x, 0, 1),),), 0, ())


def small_space(columns=None):
    q = SpaceQueen()
    pool = [INITIAL, Bundle(0), Bundle(1)]
    columns = columns or [[response(0), response(0), response(1)],
                          [response(0), response(1), response(1)]]
    refs = [q.add('unit_intervention_support', {'index': i}) for i in range(len(columns))]
    return q, CausalSpace(q, pool, columns, refs), refs


class MechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = episode(1)

    def test_existing_queen_inheritance(self):
        self.assertIsInstance(SpaceQueen(), Queen)

    def test_spatial_path_executes(self):
        q, w = make_queen(0)
        self.assertTrue(q.r_valid())

    def test_persistent_instance(self):
        self.assertTrue(self.archive['same_queen'] and self.archive['same_ledger'])
        self.assertEqual(len(self.archive['rounds']), 6)

    def test_actual_source_binding(self):
        q = SpaceQueen(); q.allocator.ast = 0
        with self.assertRaises(PermissionError): q.require_allocator()

    def test_scale_binding(self):
        q = SpaceQueen(); q.allocator_bundle = Bundle(INITIAL.ast, .5)
        with self.assertRaises(PermissionError): q.require_allocator()

    def test_scale_changes_identity(self):
        self.assertNotEqual(INITIAL.key, Bundle(INITIAL.ast, .5).key)

    def test_bad_scale_rejected(self):
        with self.assertRaises(ValueError): Bundle(0, 7)

    def test_bad_opcode_rejected(self):
        with self.assertRaises(ValueError): Bundle(('exec', 0, 1))

    def test_oversized_program_rejected(self):
        t = 0
        for _ in range(8): t = ('+', t, 1)
        with self.assertRaises(ValueError): Bundle(t)

    def test_counterexample_splits_equivalence(self):
        _, s, _ = small_space()
        self.assertEqual(s.splits, [[0, 1, 2], [1, 2, 3]])

    def test_symmetry(self):
        _, s, _ = small_space()
        for i in range(3):
            for j in range(3): self.assertEqual(s.distance(i,j), s.distance(j,i))

    def test_triangle(self):
        _, s, _ = small_space()
        for i in range(3):
            for j in range(3):
                for k in range(3): self.assertLessEqual(s.distance(i,k), s.distance(i,j)+s.distance(j,k))

    def test_axis_relabeling_invariance(self):
        _, s, _ = small_space()
        rows = s.signature_rows
        for i in range(3):
            for j in range(3):
                self.assertEqual(s.distance(i,j), sum(x!=y for x,y in zip(rows[i][::-1], rows[j][::-1]))/2)

    def test_graph_reconstruction(self):
        _, s, _ = small_space()
        self.assertEqual(s.matrix(), s.matrix('graph'))

    def test_identical_program_effect_is_local_zero(self):
        _, s, _ = small_space([[response(0), response(0), response(1)]])
        self.assertEqual(s.distance(0,1), 0)
        self.assertEqual(len(set(s.groups)), 2)

    def test_redundant_coordinate_not_new_dimension(self):
        _, s, _ = small_space([[response(0), response(0), response(1)]]*3)
        self.assertEqual(len(s.axes), 1)

    def test_empty_space_is_unknown(self):
        with self.assertRaises(ValueError): CausalSpace(SpaceQueen(), [INITIAL], [], [])

    def test_missing_response_rejected(self):
        with self.assertRaises(ValueError): small_space([[response(0)]])

    def test_withdrawal_stops_distance_use(self):
        q,s,refs=small_space();q.ledger.revoke(refs[0], 'test')
        with self.assertRaises(PermissionError): s.distance(0,1)

    def test_withdrawal_preserves_reference(self):
        q,s,refs=small_space();body=q.ledger.records[refs[0]].body;q.ledger.revoke(refs[0], 'test')
        r=q.add('historical_revisit', {}, refs=(refs[0],))
        self.assertNotIn(r,q.ledger.invalid);self.assertEqual(body,q.ledger.records[refs[0]].body)

    def test_wrong_association_changes_geometry(self):
        _,s,_=small_space();self.assertNotEqual(s.matrix()[1],s.matrix('shuffled')[1])

    def test_collapsed_space_is_not_informative(self):
        _,s,_=small_space();groups,d=s.matrix('collapsed')
        self.assertEqual(len(set(groups)),1);self.assertFalse(any(any(row) for row in d))

    def test_counterfactual_cache_not_counted_new(self):
        e=InterventionEngine([0,'info'],[problems(0)])
        e.run(INITIAL,0);n=e.cost['interventions_executed'];e.run(INITIAL,0)
        self.assertEqual(n,e.cost['interventions_executed']);self.assertEqual(e.cost['intervention_cache_hits'],1)

    def test_independent_interpreter(self):
        blocks=problems(7);e=InterventionEngine([0,'info','price'],[blocks])
        actual=e.run(INITIAL,0).json()
        formatted=[({'masks':p.masks,'prices':p.prices,'count':p.count},h) for p,h in blocks]
        self.assertTrue(equal(actual,reference_intervention(INITIAL.json(),e.tasks,formatted)))

    def test_acquisition_only_receives_ports(self):
        q=SpaceQueen();block,ref=q.acquire(opaque_problems(8))
        self.assertEqual(len(block),6)
        self.assertEqual(len(json.loads(q.ledger.records[ref].body)['cases']),6)

    def test_finite_bank_not_distribution_certificate(self):
        class Fake:
            blocks=[0,1,2,3]
            def run(self,b,j):return response(0,.1 if b.key==INITIAL.key else .08)
        after,r=adoption(INITIAL,Bundle(0),Fake())
        self.assertNotEqual(after.key,INITIAL.key)
        self.assertEqual(r['certificate']['distribution_certificate'],'UNKNOWN')
        self.assertLess(r['certificate']['hoeffding_single_comparison_lcb'],0)

    def test_fresh_proposals_are_ordered(self):
        x=self.archive
        for r in x['rounds']:
            deps=x['ledger'][r['check_record']]['deps']
            self.assertTrue(all(k>=r['proposal_record'] for k in deps))

    def test_graph_strong_control(self):
        self.assertTrue(self.archive['summary']['graph_identical'])

    def test_pressure_reaches_actual_entry(self):
        self.assertTrue(self.archive['pressure']['entry_stopped'])

    def test_complete_archive_replay(self):
        self.assertTrue(verify_episode(self.archive)['passed'])

    def test_json_list_tuple_replay(self):
        self.assertTrue(verify_episode(json.loads(json.dumps(self.archive)))['passed'])

    def test_numerical_tamper_detected(self):
        bad=copy.deepcopy(self.archive);bad['rounds'][0]['proposal_interventions'][0]['loss']+=.1
        with self.assertRaises(ValueError):verify_episode(bad)

    def test_forward_dependency_detected(self):
        bad=copy.deepcopy(self.archive);bad['ledger'][0]['deps']=[1]
        with self.assertRaises(ValueError):verify_episode(bad)

    def test_false_cost_detected(self):
        bad=copy.deepcopy(self.archive);bad['actual_cost']['actual_queries']+=1
        with self.assertRaises(ValueError):verify_episode(bad)

    def test_graph_plain_full_trajectory(self):
        other=episode(1,plain=True)
        # Read counts differ due to graph reconstruction; stored behavior and evidence do not.
        self.assertTrue(equal(self.archive['rounds'],other['rounds']))
        self.assertTrue(equal(self.archive['ledger'],other['ledger']))


if __name__=='__main__':
    unittest.main(verbosity=2)
