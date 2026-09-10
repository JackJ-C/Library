"""固定全集实验，结果由代码生成，结论与失败分别记录。"""
from collections import Counter
from itertools import combinations, product
from fractions import Fraction
from math import comb
import random
from .engine import Model, World, QUERIES, Trace, Probe, Controller, episode, repair, validate


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def span(rows):
    values = {0}
    for row in rows:
        values |= {v ^ row for v in tuple(values)}
    return values


def theorem_checks():
    rows = []
    for p in QUERIES:
        row = p.context << 6
        for j in range(3):
            if (p.route >> j) & 1:
                row |= p.context << (2 * j)
        rows.append(row)
    counts, example = {}, None
    for size in range(17):
        good = []
        for ids in combinations(range(16), size):
            if {21, 42} <= span([rows[i] for i in ids]):
                good.append(ids)
        counts[str(size)] = dict(subsets=sum(1 for _ in combinations(range(16), size)),
                                 sufficient=len(good))
        if good and example is None:
            example = good[0]
    require(all(counts[str(k)]["sufficient"] == 0 for k in range(4)), "lower bound")
    require(example is not None, "matching upper bound")
    # 全部三个非空可接受修复集合（每集合是三个动作的子集）。
    overlap, pairwise_only = 0, 0
    for a, b, c in product(range(1, 8), repeat=3):
        common = a & b & c
        feasible = any(all(s & (1 << r) for s in (a, b, c)) for r in range(3))
        require(bool(common) == feasible, "repair intersection criterion")
        overlap += 1
        pairwise_only += int(bool(a & b) and bool(a & c) and bool(b & c) and not common)
    exact_mean = sum((Fraction(comb(16, k) - counts[str(k)]["sufficient"], comb(16, k))
                      for k in range(16)), Fraction())
    return dict(query_subset_counts=counts, minimal_probe_count=4, example_queries=example,
                uniform_random_exact_mean=str(exact_mean), uniform_random_exact_float=float(exact_mean),
                full_identity_lower_bound_bits=8, repair_set_families=overlap,
                pairwise_but_not_joint=pairwise_only)


def run_study():
    m = Model()
    cases, random_rows, transitions = [], [], []
    example = None
    for h in range(256):
        sensor = World(h).step
        controller = Controller(m, sensor)
        a, checked = controller.cycle()
        deployment = a.pop("deployment")
        flat = episode(m, sensor, "flat", scope="system-A/0")
        identity = episode(m, sensor, "identity")
        passive = episode(m, sensor, "passive", order=[7, 15] * 8)
        require(a == flat, "same-information flat control differs")
        require(a["repair"] == repair(h) and checked["accepted"], "repair correctness")
        require(identity["state"] == 1 << h, "component attribution")
        require(passive["repair"] is None, "passive ambiguity unexpectedly removed")
        baseline = sum(r["old_ok"] for r in checked["rows"])
        deployed = sum(controller.act(Probe(x, 7), payload=b, neutral=True) == b
                       for x in range(4) for b in (0, 1))
        require(deployed == 8, "persistent deployment failed")
        cases.append(dict(world=h, target=repair(h), selected=a["repair"],
                          queries=len(a["queries"]), identity_queries=len(identity["queries"]),
                          residual_models=a["state"].bit_count(), baseline=baseline,
                          after=deployed, deployed_version=deployment["new_version"],
                          status=checked["status"], flat_equal=True))
        if h == 85:
            example = dict(world_for_evaluator_only=h, agent_trace=a["trace"],
                           independent_validation=checked, deployment=deployment)
        for seed in range(64):
            order = list(range(16))
            random.Random(seed).shuffle(order)
            r = episode(m, sensor, "random", order=order)
            require(r["repair"] == repair(h), "random eventual correctness")
            random_rows.append((h, seed, len(r["queries"])))
        for changed in (0, 3):
            for delta in (1, 2, 3):
                new_h = h ^ (delta << (2 * changed))
                new_sensor = World(new_h).step
                moved = m.transition(a["state"], (changed,))
                b = episode(m, new_sensor, initial=moved)
                reset = episode(m, new_sensor)
                blind_gate = validate(new_sensor, a["repair"], a["repair"])
                require(b["repair"] == repair(new_h), "transported certificate failure")
                require((moved >> new_h) & 1, "truth excluded during transition")
                transitions.append(dict(world=h, component=changed, delta=delta,
                                        transported_queries=len(b["queries"]),
                                        reset_queries=len(reset["queries"]),
                                        blind_wrong=a["repair"] != repair(new_h),
                                        blind_gate_rejected=not blind_gate["accepted"]))
    # 两个不同 Worker 共享通信、Queen 执行通道和环境，共 4**5 个组合。
    # B 只继承共享部件的证据约束，不继承 A 的 Worker 参数或第一人称经历。
    multiworker = Counter()
    for h_a in range(256):
        first = episode(m, World(h_a).step, "identity", scope="team/worker-A")
        shared = m.transition(first["state"], (0,))
        for worker_b in range(4):
            h_b = (h_a & ~3) | worker_b
            second = episode(m, World(h_b).step, "identity", initial=shared, scope="team/worker-B")
            require(second["state"] == 1 << h_b, "multi-worker attribution")
            multiworker[len(first["queries"]) + len(second["queries"])] += 1
    nonlinear_rejected = 0
    provenance_conflicts = 0
    for h in range(256):
        w = World(h, nonlinear=True)
        a = episode(m, w.step)
        nonlinear_rejected += not validate(w.step, 0, a["repair"])["accepted"]
        a = episode(m, World(h).step, scope="A")
        b = episode(m, World(h ^ 1).step, scope="B")
        own = [r for r in a["trace"] if r["kind"] == "observation"]
        other = [r for r in b["trace"] if r["kind"] == "observation"]
        require(m.replay(own) == a["state"], "provenance retained")
        provenance_conflicts += m.replay(own + other) == 0
    require(nonlinear_rejected == 256 and provenance_conflicts == 256, "negative controls")
    summaries = {}
    for component in (0, 3):
        subset = [r for r in transitions if r["component"] == component]
        summaries[str(component)] = dict(cases=len(subset),
            transported_histogram=dict(Counter(r["transported_queries"] for r in subset)),
            reset_histogram=dict(Counter(r["reset_queries"] for r in subset)),
            blind_wrong=sum(r["blind_wrong"] for r in subset),
            blind_gate_rejected=sum(r["blind_gate_rejected"] for r in subset))
    require(all(len({q for _, s, q in random_rows if s == seed}) == 1 for seed in range(64)),
            "random seed summary would conceal world dependence")
    result = dict(
        M1=dict(worlds=256, automatic_trace_example_world=85),
        M2=dict(library_correct=256, flat_equal=256, passive_abstentions=256,
                random_runs=len(random_rows),
                random_query_histogram=dict(Counter(r[2] for r in random_rows)),
                random_mean_queries=sum(r[2] for r in random_rows) / len(random_rows),
                library_query_histogram=dict(Counter(r["queries"] for r in cases)),
                random_seed_counts={str(seed): next(r[2] for r in random_rows if r[1] == seed)
                                    for seed in range(64)}),
        M3=dict(adopted=sum(r["status"] == "adopt" for r in cases),
                no_change=sum(r["status"] == "no_change" for r in cases),
                regressed=sum(r["after"] < r["baseline"] for r in cases),
                baseline_correct=sum(r["baseline"] for r in cases),
                repaired_correct=sum(r["after"] for r in cases), tasks=256 * 8,
                validation_sensor_calls_per_world=16, post_deployment_sensor_calls_per_world=8),
        M4=dict(exact_attribution=256,
                identity_query_histogram=dict(Counter(r["identity_queries"] for r in cases)),
                repair_residual_models=dict(Counter(r["residual_models"] for r in cases)),
                foreign_scope_conflicts=provenance_conflicts,
                multiworker_worlds=1024, multiworker_exact_attribution=1024,
                shared_evidence_query_histogram=dict(multiworker),
                separate_identification_queries=16, multiworker_lower_bound_bits=10),
        M5=summaries,
        M6=dict(theorems=theorem_checks(), nonlinear_confident_proposals=256,
                nonlinear_rejected_by_independent_gate=nonlinear_rejected,
                flat_log_advantage_claim="not_supported",
                open_ended_self_evolution="not_tested"))
    return result, cases, random_rows, transitions, example
