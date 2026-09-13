"""R30: bounded causal-space experiment on the existing R3/M54 Queen.

All inherited files are unchanged. A new, disclosed wrapper adds a two-level
allocator experiment, using the existing R23 allocator interpreter and R4 task
interpreter. It does NOT reconstruct missing R24-R27 implementation files.
No imports or calls for network, paid compute, process spawning or replication.
"""
from collections import Counter
from dataclasses import dataclass, asdict
from math import sqrt, log
from random import Random
from statistics import mean

from src.core import Queen, World, Port
from r4_r7 import search
from r20_r23_recovery import racing
from .space import CausalSpace, Response, canonical, digest, freeze

GENERATIONS = 6
META_COUNT = 8
TASK_COUNT = 6
INNER_BUDGET = 12
FULL_CANDIDATES = 2
PILOTS = 3
HISTORY_BLOCKS = 6
ADOPTION_BLOCKS = 4
TEST_BLOCKS = 6
TRAIN_CASES = 4
TEST_CASES = 2
EPS = 1e-12
FINITE_BANK_MARGIN = 0.002
SCALES = (0.5, 1.0, 2.0)
MODES = ("space", "raw", "frozen")
SHADOWS = ("graph", "raw", "shuffled", "collapsed", "previous", "initial")


@dataclass(frozen=True)
class Bundle:
    ast: tuple | str | int
    scale: float = 1.0

    def __post_init__(self):
        object.__setattr__(self, "ast", racing.freeze(self.ast))
        racing.Program(self.ast)
        if self.scale not in SCALES:
            raise ValueError("scale outside frozen grammar")

    @property
    def key(self):
        return digest([self.ast, self.scale])

    def json(self):
        return {"ast": self.ast, "scale": self.scale, "key": self.key}


INITIAL = Bundle(racing.INITIAL)


def candidate_pool(parent, seed):
    asts = racing.candidates(parent.ast, seed, META_COUNT)
    rng = Random(seed ^ 731)
    return [parent] + [Bundle(a, rng.choice(SCALES)) for a in asts[1:]]


def task_pool(parent, seed):
    return [parent] + search.pool(parent, seed, TASK_COUNT - 1)


def problems(seed):
    rng = Random(seed)
    return [search.make_problem(rng.randrange(1 << 50), n=16, nq=12)
            for _ in range(TRAIN_CASES + TEST_CASES)]


def opaque_problems(seed):
    return [(p, search.Body(p, hidden)) for p, hidden in problems(seed)]


def serialize_problem(p):
    return {"masks": p.masks, "prices": p.prices, "count": p.count}


def cost_bound(p):
    return 9 * len(p.masks)


class SpaceQueen(Queen):
    def __init__(self, seed=0, plain=False):
        super().__init__(seed, "plain" if plain else "library")
        self.allocator_bundle = INITIAL
        self.allocator = racing.Program(INITIAL.ast)
        self.search_program = search.Program(0)
        self.bundle_permission = None
        self.bundle_binding = None
        self.history = []
        self.block_refs = []
        self.space_versions = []
        self.compute_cost = Counter()
        self.own_diagnostic_cost = search.Cost()
        self.previous_allocator = INITIAL
        self.bind_allocator(INITIAL, ())

    def bind_allocator(self, bundle, supports):
        self.allocator_bundle = bundle
        self.allocator = racing.Program(bundle.ast)
        self.bundle_binding = (id(self.allocator), bundle.key)
        self.bundle_permission = self.add("R30_allocator_binding", {
            "bundle": bundle.json(),
            "scope": "conditional finite diagnostic learning protocol",
            "future_distribution_certified": False
        }, deps=tuple(dict.fromkeys(supports)))

    def require_allocator(self):
        if (self.bundle_permission in self.ledger.invalid or
                self.bundle_binding != (id(self.allocator), self.allocator_bundle.key) or
                racing.freeze(self.allocator.ast) != self.allocator_bundle.ast):
            raise PermissionError("withdrawn or changed complete allocator binding")
        return self.allocator_bundle

    def acquire(self, opaque_cases):
        """The fixture selects opaque mechanisms; the Queen sees only query replies.
        The caller supplies only public hypotheses and opaque response ports.
        Target IDs and fixture seeds do not enter this method.
        """
        self.require_allocator()
        cases, rows, roots = [], [], []
        for p, body in opaque_cases:
            intention = self.add("R30_diagnostic_intention", {
                "problem": serialize_problem(p), "program": self.search_program.ast,
                "allocator_binding": self.bundle_permission
            }, refs=(self.bundle_permission,))
            price, remaining, transcript = search.solve(
                p, body, self.search_program, self.own_diagnostic_cost, actual=True)
            if remaining.bit_count() != 1:
                raise RuntimeError("the declared separating basis failed")
            inferred = remaining.bit_length() - 1
            receipt = self.add("R30_diagnostic_observation", {
                "intention": intention, "transcript": transcript,
                "inferred_mechanism": inferred, "price": price
            }, refs=(intention,))
            rows.append({"problem": serialize_problem(p), "inferred": inferred,
                         "intention": intention, "receipt": receipt})
            roots += [intention, receipt]
            cases.append((p, inferred))
        record = self.add("R30_observed_block", {"cases": rows}, deps=tuple(roots))
        return cases, record

    def remember(self, block, record):
        self.history.append(block)
        self.block_refs.append(record)
        self.history = self.history[-HISTORY_BLOCKS:]
        self.block_refs = self.block_refs[-HISTORY_BLOCKS:]


class InterventionEngine:
    """Runs program replacements on previously observed or evaluator-only blocks.
    Model evaluations and physical/opaque-response queries are counted separately.
    Cache reuse is never claimed to be a new independent observation.
    """
    def __init__(self, tasks, blocks):
        self.tasks = tasks
        self.blocks = blocks
        self.loss_cache = {}
        self.response_cache = {}
        self.cost = Counter()

    def task_response(self, arm, block_index, case_index):
        self.cost["task_loss_requests"] += 1
        key = (arm, block_index, case_index)
        if key not in self.loss_cache:
            p, inferred = self.blocks[block_index][case_index]
            counts = search.Cost()
            price, remaining, trace = search.solve(
                p, search.Body(p, inferred), search.Program(self.tasks[arm]), counts)
            loss = price / cost_bound(p) if remaining.bit_count() == 1 else 1.0
            if not 0 <= loss <= 1:
                raise RuntimeError("normalization bound failed")
            signature = tuple((r["query"], r["value"], r["price"]) for r in trace)
            self.loss_cache[key] = (loss, signature)
            self.cost.update({"simulated_queries": counts.simulated_queries,
                              "task_ast_ops": counts.ast_ops,
                              "task_feature_ops": counts.feature_ops,
                              "simulated_query_price": price})
        else:
            self.cost["task_cache_hits"] += 1
        return self.loss_cache[key]

    def run(self, bundle, block_index):
        self.cost["intervention_requests"] += 1
        key = (bundle.key, block_index)
        if key in self.response_cache:
            self.cost["intervention_cache_hits"] += 1
            return self.response_cache[key]
        self.cost["interventions_executed"] += 1
        chosen, trace = racing.race(
            racing.Program(bundle.ast), self.tasks,
            lambda arm, j: self.task_response(arm, block_index, j % TRAIN_CASES)[0],
            budget=INNER_BUDGET, scale=bundle.scale, costs=self.cost)
        checks = [self.task_response(chosen, block_index, j)
                  for j in range(TRAIN_CASES, TRAIN_CASES + TEST_CASES)]
        result = Response(mean(x[0] for x in checks),
                          tuple(x[1] for x in checks), chosen,
                          tuple((r["arm"], r["sample"], r["loss"]) for r in trace["trace"]))
        self.response_cache[key] = result
        return result

    def average(self, bundle, indices):
        return mean(self.run(bundle, j).loss for j in indices)

    def export(self):
        return [{"bundle": key[0], "block": key[1], **value.json()}
                for key, value in sorted(self.response_cache.items())]


def choose_proposal(parent, proposer, pool, space, engine, mode):
    """Same raw pilot evidence for all arms. Geometry changes its use, not its truth.
    Every arm is permitted exactly FULL_CANDIDATES further candidate evaluations.
    Data acquisition is shared for matched shadows, not falsely attributed to them.
    """
    pilot_indices = list(range(min(PILOTS, len(engine.blocks) - 1)))
    dev_indices = list(range(len(pilot_indices), len(engine.blocks)))
    if not dev_indices:
        raise ValueError("separate proposal-check block required")
    pilots = [[engine.run(b, j).loss for j in pilot_indices] for b in pool]
    averages = [mean(row) for row in pilots]
    best_mean = min(averages)
    geometry_mode = mode if mode in ("graph", "shuffled", "collapsed") else "space"
    groups, distances = space.matrix(geometry_mode)
    use_geometry = mode != "raw"
    selector = racing.Program(proposer.ast)
    chosen = []
    selected_groups = set()
    ranking_records = []
    for _ in range(FULL_CANDIDATES):
        eligible = [i for i in range(1, len(pool)) if i not in chosen]
        if use_geometry:
            novel = [i for i in eligible if groups[i] not in selected_groups]
            if novel:
                eligible = novel
        priorities = []
        for i in eligible:
            var = mean((x - averages[i]) ** 2 for x in pilots[i])
            novelty = min((distances[i][j] for j in [0] + chosen), default=0)
            uncert = sqrt((var + 0.0001) / len(pilot_indices))
            if use_geometry:
                uncert += 0.025 * novelty
            features = (averages[i], proposer.scale * uncert,
                        len(pilot_indices) / (len(pilot_indices) + len(dev_indices)),
                        averages[i] - best_mean)
            score = selector(features, engine.cost)
            priorities.append((score, racing.size(pool[i].ast), pool[i].key, i, features))
        if not priorities:
            break
        winner = min(priorities)
        i = winner[3]
        chosen.append(i)
        selected_groups.add(groups[i])
        ranking_records.append({"eligible": eligible, "chosen": i,
                                "priorities": [[p[3], p[0], p[4]] for p in priorities]})
    scored = [(engine.average(pool[i], dev_indices),
               0 if i == 0 else 1, racing.size(pool[i].ast), pool[i].key, i)
              for i in [0] + chosen]
    proposed = min(scored)[-1]
    return pool[proposed], {"mode": mode, "proposer": proposer.json(),
                           "pilot_means": averages, "shortlist": chosen,
                           "proposal": proposed, "scores": [[x[-1], x[0]] for x in scored],
                           "ranking": ranking_records,
                           "logical_full_checks": len(chosen) * len(dev_indices)}


def adoption(parent, candidate, engine):
    old = [engine.run(parent, j).loss for j in range(len(engine.blocks))]
    new = [engine.run(candidate, j).loss for j in range(len(engine.blocks))]
    accepted = (candidate.key != parent.key and
                mean(old) - mean(new) > FINITE_BANK_MARGIN)
    # The imported conservative certificate is reported, never silently faked.
    n = len(new)
    radius = sqrt(2 * log(2 / 0.05) / n)
    certificate = {"scope": "exact observed finite adoption bank, not future distribution",
                   "independent_blocks": n,
                   "empirical_gain": mean(old) - mean(new),
                   "hoeffding_single_comparison_lcb": mean(old) - mean(new) - radius,
                   "distribution_certificate": "UNKNOWN"}
    return candidate if accepted else parent, {"accepted": accepted, "old": old,
                                               "new": new, "certificate": certificate}


def make_queen(seed, plain=False):
    q = SpaceQueen(seed, plain)
    rng = Random(seed)
    gain = rng.randrange(1, 7)
    w = World((1, 0, "less", 3, (gain, 2, 3, 4)))
    w.bias = [rng.randrange(7), rng.randrange(7)]
    diagnosed = q.diagnose(Port(w))
    if diagnosed["status"] != "adopted":
        raise RuntimeError("inherited spatial Queen did not initialize")
    step = q.step(Port(w), 0, 3)
    if not step["executed"] or step["mismatch"]:
        raise RuntimeError("inherited task continuity failed")
    return q, w


def episode(seed, mode="space", plain=False):
    if mode not in MODES:
        raise ValueError("unknown sustained method")
    q, w = make_queen(seed, plain)
    identities = (id(q), id(q.ledger))
    for j in range(3):
        block, ref = q.acquire(opaque_problems(seed * 100000 + j))
        q.remember(block, ref)
    rounds = []
    previous_was_adoption = False
    for generation in range(GENERATIONS):
        parent = q.require_allocator()
        old_previous = q.previous_allocator
        old_task = q.search_program.ast
        block, ref = q.acquire(opaque_problems(seed * 100000 + 100 + generation))
        q.remember(block, ref)
        tasks = task_pool(old_task, seed * 71 + generation)
        pool = candidate_pool(parent, seed * 131 + generation)
        engine = InterventionEngine(tasks, q.history)
        n_pilots = min(PILOTS, len(q.history) - 1)
        columns = [[engine.run(b, j) for b in pool] for j in range(n_pilots)]
        space = CausalSpace(q, pool, columns, q.block_refs[:n_pilots])
        q.space_versions.append(space.version)
        actual_proposer = INITIAL if mode == "frozen" else parent
        actual_geometry = "raw" if mode == "raw" else "space"
        candidate, primary = choose_proposal(parent, actual_proposer, pool, space,
                                             engine, actual_geometry)
        branches = {"primary": (candidate, primary)}
        for shadow in SHADOWS:
            proposer = old_previous if shadow == "previous" else INITIAL if shadow == "initial" else parent
            geometry = "space" if shadow in ("previous", "initial") else shadow
            branches[shadow] = choose_proposal(parent, proposer, pool, space, engine, geometry)
        # Freeze every proposal and its complete configuration BEFORE adoption data.
        proposal_record = q.add("R30_frozen_proposals", {
            "parent": parent.json(), "previous": old_previous.json(),
            "pool": [b.json() for b in pool], "tasks": tasks,
            "space": space.public(),
            "branches": {k: {"candidate": v[0].json(), "selection": v[1]}
                         for k, v in branches.items()},
            "history_records": list(q.block_refs)
        }, deps=(space.version,) + tuple(q.block_refs))
        newly_observed, new_refs = [], []
        for j in range(ADOPTION_BLOCKS):
            block, ref = q.acquire(opaque_problems(seed * 100000 + 1000 + generation * 20 + j))
            newly_observed.append(block)
            new_refs.append(ref)
        adoption_engine = InterventionEngine(tasks, newly_observed)
        successors = {}
        checks = {}
        for name, (candidate, _) in branches.items():
            successors[name], checks[name] = adoption(parent, candidate, adoption_engine)
        child = successors["primary"]
        adopted = child.key != parent.key
        check_record = q.add("R30_complete_bundle_check", {
            "proposal_record": proposal_record, "checks": checks,
            "deployed": child.json(), "provisional_empirical_adoption": True,
            "future_distribution_certified": False
        }, deps=(proposal_record,) + tuple(new_refs))
        q.previous_allocator = parent
        q.bind_allocator(child, (check_record,))
        if mode == "space" and successors["graph"].key != child.key:
            raise RuntimeError("information-equivalent graph reconstruction diverged")
        # The accepted allocator REALLY selects the solver used on later own cases.
        chosen = adoption_engine.run(child, 0).task
        q.search_program = search.Program(tasks[chosen])
        q.add("R30_actual_task_binding", {"before": old_task, "after": q.search_program.ast,
              "allocator": child.json(), "used_for_next_actual_diagnosis": True},
              deps=(q.bundle_permission,))
        q.require_allocator()
        # Evaluator-only problems are constructed only after all choices are fixed.
        evaluation_blocks = [problems(seed * 100000 + 5000 + generation * 20 + j)
                             for j in range(TEST_BLOCKS)]
        evaluator = InterventionEngine(tasks, evaluation_blocks)
        test_bundles = {"parent": parent, "child": child, **successors}
        outcomes = {name: [evaluator.run(b, j).loss for j in range(TEST_BLOCKS)]
                    for name, b in test_bundles.items()}
        means = {name: mean(values) for name, values in outcomes.items()}
        delta = means["parent"] - means["child"]
        gamma_previous = means["previous"] - means["child"]
        gamma_initial = means["initial"] - means["child"]
        strict = (generation > 0 and previous_was_adoption and adopted and
                  min(delta, gamma_previous, gamma_initial) > EPS)
        step = q.step(Port(w), generation % 2, (generation + 4) % 7)
        if not step["executed"] or step["mismatch"]:
            raise RuntimeError("inherited spatial continuity lost")
        if identities != (id(q), id(q.ledger)):
            raise RuntimeError("persistent subject replaced")
        round_record = {
            "generation": generation, "parent": parent.json(), "child": child.json(),
            "adopted": adopted, "previous_adopted": previous_was_adoption,
            "strict_empirical_link": strict, "delta": delta,
            "gamma_previous": gamma_previous, "gamma_initial": gamma_initial,
            "space": space.public(), "proposal_record": proposal_record,
            "check_record": check_record,
            "geometry_changes_proposal": branches["raw"][0].key != branches["primary"][0].key,
            "wrong_association_changes_proposal": branches["shuffled"][0].key != branches["primary"][0].key,
            "graph_proposal_identical": branches["graph"][0].key == branches["primary"][0].key,
            "checks": checks,
            "evaluation_only": {"means": means, "blocks": outcomes},
            "proposal_cost": dict(engine.cost), "adoption_cost": dict(adoption_engine.cost),
            "evaluator_cost": dict(evaluator.cost),
            "proposal_interventions": engine.export(),
            "adoption_interventions": adoption_engine.export(),
            "spatial_step": step,
        }
        rounds.append(round_record)
        previous_was_adoption = adopted
        # Only actually experienced adoption data enters future histories, never test data.
        for block, ref in zip(newly_observed, new_refs):
            q.remember(block, ref)
    # Revoke a genuine support and verify the actual entry point stops.
    root = new_refs[-1]
    original = q.ledger.records[root].body
    invalidated = q.ledger.revoke(root, "R31 actual adoption support withdrawal")
    stopped = False
    try:
        q.require_allocator()
    except PermissionError:
        stopped = True
    revisit = q.add("R31_revisit_withdrawn_history", {"event_remains_historical": True}, refs=(root,))
    pressure = {"withdrawn_root": root, "invalidated": invalidated,
                "entry_stopped": stopped,
                "body_unchanged": q.ledger.records[root].body == original,
                "reference_survives": revisit not in q.ledger.invalid,
                "recomputed_invalidity_matches": q.ledger.recompute() == q.ledger.invalid}
    flags = [r["strict_empirical_link"] for r in rounds]
    summary = {"updates": sum(r["adopted"] for r in rounds),
               "strict_empirical_links": sum(flags),
               "adjacent_links": any(a and b for a, b in zip(flags, flags[1:])),
               "regressions": sum(r["delta"] < -EPS for r in rounds),
               "mean_test_loss": mean(r["evaluation_only"]["means"]["child"] for r in rounds),
               "mean_recursive_gain": mean(r["gamma_initial"] for r in rounds[1:]),
               "mean_geometry_gain": mean(r["evaluation_only"]["means"]["raw"] -
                                          r["evaluation_only"]["means"]["child"] for r in rounds),
               "mean_dimension": mean(r["space"]["dimension"] for r in rounds),
               "mean_classes": mean(r["space"]["classes"] for r in rounds),
               "changed_proposals": sum(r["geometry_changes_proposal"] for r in rounds),
               "graph_identical": all(r["graph_proposal_identical"] for r in rounds)}
    return {"seed": seed, "mode": mode, "same_queen": True, "same_ledger": True,
            "lineage": "R3 Queen -> M54 Queen -> M8 Ledger; R23 allocator/R4 solver unchanged",
            "summary": summary, "pressure": pressure,
            "actual_cost": asdict(q.own_diagnostic_cost),
            "ledger_read_cost": dict(q.cost), "rounds": rounds,
            "ledger": q.ledger.export(), "invalid": sorted(q.ledger.invalid)}
