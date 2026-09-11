"""全量有限实验。模拟器/评估器可持真值；学习器仅接观察。"""
from collections import Counter
from itertools import product
from random import Random
from .core import (Ledger, PolynomialReader, World, acceptable, bits, features,
                   majority_error, monomials, repetitions, require, solve)


def true_degree(table, d):
    # 独立于拟合器的布尔 Möbius 变换，仅评估使用。
    coefficients = [(table >> x) & 1 for x in range(1 << d)]
    for i in range(d):
        for x in range(1 << d):
            if x & (1 << i):
                coefficients[x] ^= coefficients[x ^ (1 << i)]
    return max((bits(x) for x, value in enumerate(coefficients) if value), default=0)


def table_from_coefficients(coefficients, d, degree):
    terms = monomials(d, degree)
    return sum((bits(features(x, terms) & coefficients) & 1) << x
               for x in range(1 << d))


def m8():
    rows, counts = [], Counter()
    trace = None
    order = sorted(range(8), key=lambda x: (bits(x), x))
    for truth in range(256):
        world = World(3, truth, truth ^ 0xA5)
        reader = PolynomialReader(3)
        observations, initial = [], None
        for x in order:
            value = world.paired(x)
            observations.append((x, value))
            reader.observe(x, value)
            if len(observations) == 4:
                initial = reader.table()
        require(not reader.failed and reader.table() == truth, "M8 full recovery")
        require(reader.certify_full_universe(), "M8 full scope certificate")
        # 同信息普通日志：一次性重算最小可行次数，不读取递归复查记录。
        plain = None
        for degree in range(1, 4):
            terms = monomials(3, degree)
            fitted = solve((features(x, terms), y) for x, y in observations)
            if fitted is not None:
                plain = table_from_coefficients(fitted[0], 3, degree)
                break
        require(plain == truth, "plain log must agree")
        maximal_world = World(3, truth, truth ^ 0xA5)
        maximal_terms = monomials(3, 3)
        maximal_observations = [(x, maximal_world.paired(x)) for x in order]
        maximal = solve((features(x, maximal_terms), y) for x, y in maximal_observations)
        require(maximal is not None and table_from_coefficients(maximal[0], 3, 3) == truth,
                "maximal grammar baseline")
        require(maximal_observations == observations and maximal_world.calls == world.calls,
                "same observations and interaction budget")
        counts["maximal_grammar_correct"] += 1
        terms = monomials(3, 1)
        fixed = solve((features(x, terms), y) for x, y in observations)
        counts["fixed_model_rejected"] += fixed is None
        counts["early_unconditional_wrong"] += initial != truth
        counts["expanded_worlds"] += bool(reader.expansions)
        counts["expansion_events"] += len(reader.expansions)
        counts["degree_" + str(reader.degree)] += 1
        before = sum(world.execute(x, b) == b for x in range(8) for b in (0, 1))
        world.correction = reader.predict
        after = sum(world.execute(x, b) == b for x in range(8) for b in (0, 1))
        require(after == 16 and world.calls == 16, "actual correction / query count")
        counts["before_correct"] += before
        counts["after_correct"] += after
        rows.append([truth, true_degree(truth, 3), reader.degree, reader.expansions,
                     initial, before, after, reader.refits, len(reader.ledger.invalid)])
        if truth == 128:
            trace = reader.ledger.export()
    # 四变量二次族，11 个训练输入，5 个冻结后挑战输入。
    train = [x for x in range(16) if bits(x) <= 2]
    train.sort(key=lambda x: (bits(x), x))
    holdout = [x for x in range(16) if bits(x) > 2]
    quadratic, outside = [], []
    for coefficients in range(1 << 11):
        truth = table_from_coefficients(coefficients, 4, 2)
        world = World(4, truth, 0xA55A)
        reader = PolynomialReader(4, maximum=2)
        for x in train:
            reader.observe(x, world.paired(x))
        require(not reader.failed, "quadratic family fit")
        world.correction = reader.predict
        correct = sum(world.execute(x, b) == b for x in holdout for b in (0, 1))
        quadratic.append([coefficients, reader.degree, correct])
        require(correct == 10, "held-out quadratic challenge")
        # 只在包含前三个变量的输入上增加一个三次项；训练输入不受影响。
        extra = sum(1 << x for x in range(16) if x & 7 == 7)
        badworld = World(4, truth ^ extra, 0xA55A)
        require(all(badworld.paired(x) == ((truth >> x) & 1) for x in train),
                "out-of-family must be observationally identical on training")
        badworld.correction = reader.predict
        failed = sum(badworld.execute(x, b) != b for x in holdout for b in (0, 1))
        outside.append([coefficients, failed])
    require(all(r[1] == 4 for r in outside), "cubic challenge counterexample")
    summary = dict(counts)
    summary.update(worlds=256, recovered=256, plain_log_equal=256,
                   maximal_grammar_queries=8, adaptive_queries=8,
                   paired_physical_calls=16, quadratic_worlds=2048,
                   heldout_input_payload_cases=20480,
                   quadratic_correct=sum(r[2] for r in quadratic),
                   cubic_worlds_failing=len(outside),
                   cubic_challenge_failures=sum(r[1] for r in outside))
    return {"summary": summary, "world_columns": ["truth", "actual_degree", "fitted_degree",
            "expansions", "early_prediction_table", "before", "after", "refits", "invalid_records"],
            "world_rows": rows, "quadratic_columns": ["coefficient_mask", "degree", "correct_of_10"],
            "quadratic_rows": quadratic, "cubic_columns": ["coefficient_mask", "failed_of_10"],
            "cubic_rows": outside, "example_trace_truth_128": trace}


def m9():
    pairs = [(j, i) for i in range(5) for j in range(i)]
    graph_rows, visits = [], 0
    for graph in range(1 << len(pairs)):
        closure_masks = []
        for root in range(5):
            ledger = Ledger()
            for i in range(5):
                deps = tuple(j for k, (j, child) in enumerate(pairs)
                             if child == i and graph & (1 << k))
                ledger.add("claim", "Queen", {"i": i}, deps=deps)
            ledger.revoke(root, "audit")
            expected = ledger.recompute()
            require(ledger.invalid == expected, "incremental and full log differ")
            closure_masks.append(sum(1 << i for i in expected))
            visits += ledger.edges_visited
        graph_rows.append([graph, closure_masks])
    configs, expansion_tests, shrunk, emptied = 0, 0, 0, 0
    monotonic_rows = []
    for masks in product(range(1, 8), repeat=3):
        allowed = {i: {u for u in range(3) if masks[i] & (1 << u)} for i in range(3)}
        configs += 1
        n_shrunk, n_empty = 0, 0
        for subset in range(1, 8):
            small = {i for i in range(3) if subset & (1 << i)}
            for added in set(range(3)) - small:
                ka, kb = acceptable(small, allowed), acceptable(small | {added}, allowed)
                require(kb <= ka, "expansion antitonic law failed")
                # 同一对反向读取就是一致证据收紧的单调性。
                expansion_tests += 1
                n_shrunk += kb != ka
                n_empty += bool(ka) and not kb
        shrunk += n_shrunk
        emptied += n_empty
        monotonic_rows.append([list(masks), n_shrunk, n_empty])
    ledger = Ledger()
    assumption = ledger.add("assumption", "Queen/model-v1", {"family": "affine"})
    old = ledger.add("certificate", "Queen/model-v1", {"scope": "conditional"}, deps=(assumption,))
    observation = ledger.add("observation", "Worker", {"counterexample": 7})
    review = ledger.add("review", "Queen/model-v2", {"old_claim_disproved": True},
                        refs=(old, observation), deps=(observation,))
    action = ledger.add("proposal", "Queen/model-v1", {}, deps=(old,))
    ledger.revoke(assumption, "grammar expanded")
    require(ledger.invalid == {assumption, old, action}, "reference is not proof dependency")
    require(review not in ledger.invalid, "valid review of invalid claim lost")
    naive_invalid = {assumption}
    for rec in ledger.records:
        if any(parent in naive_invalid for parent in rec.deps + rec.refs):
            naive_invalid.add(rec.seq)
    require(review in naive_invalid, "all-reference invalidation ablation")
    # 删除模型依赖会留下旧证书，属于输入契约漏报而非推断器自动修复。
    omitted = Ledger()
    a = omitted.add("assumption", "Queen", {})
    c = omitted.add("certificate", "Queen", {}, refs=(a,))
    omitted.revoke(a, "changed")
    require(c not in omitted.invalid, "ablation expected stale certificate")
    return {"summary": {"graphs": len(graph_rows), "root_audits": len(graph_rows) * 5,
             "all_equal_full_log": True, "dependency_edge_visits": visits,
             "acceptance_configs": configs, "expansion_edges_tested": expansion_tests,
             "strict_shrinks": shrunk, "nonempty_to_empty": emptied,
             "reference_vs_dependency_example_passed": True,
             "omitted_dependency_stale_certificate": True,
             "all_references_ablation_loses_valid_review": True},
            "graph_columns": ["graph_bitmask", "invalid_masks_for_roots_0_to_4"],
            "graph_rows": graph_rows, "monotonic_columns": ["acceptance_masks", "shrinks", "emptied"],
            "monotonic_rows": monotonic_rows, "example_ledger": ledger.export()}


def noisy_read(world, rng, n, common_error=None):
    estimate, counts = 0, []
    for x in range(1 << world.d):
        answers = []
        for _ in range(n):
            flip = int(rng.random() < 0.1) if common_error is None else common_error
            answers.append(world.paired(x) ^ flip)
        ones = sum(answers)
        counts.append(ones)
        estimate |= int(ones > n // 2) << x
    return estimate, counts


def m10():
    order = sorted(range(8), key=lambda x: (bits(x), x))
    mask = sum(1 << x for x in order[:4])
    delta_rows, old_rows, checked = [], [], 0
    for delta in range(1, 256):
        delta_rows.append([delta, bool(delta & mask), delta & ~mask & 255])
    # 真正遍历所有旧新组合，原记录采用可无损展开的异或分解。
    for old in range(256):
        detected, missed, recovered = 0, 0, 0
        for delta, expected_detected, remaining in delta_rows:
            new = old ^ delta
            world = World(3, new, 0x35)
            observed = [world.paired(x) for x in order]
            changed = any(observed[i] != ((old >> order[i]) & 1) for i in range(4))
            table = sum(value << x for value, x in zip(observed, order))
            require(changed == expected_detected and table == new, "drift audit")
            patched = (old & ~mask) | (new & mask)
            require((patched ^ new) == remaining, "lossless transition representation")
            detected += changed
            missed += not changed
            recovered += table == new
            checked += 1
        old_rows.append([old, detected, missed, recovered])
    p, n = 0.1, 11
    noise_rows, correlated_rows = [], []
    for seed in range(4096):
        truth = seed % 256
        world = World(3, truth, 0xCA)
        estimate, counts = noisy_read(world, Random(seed), n)
        noise_rows.append([seed, truth, counts, estimate ^ truth])
        common = int(Random(seed).random() < p)
        badworld = World(3, truth, 0xCA)
        badestimate, _ = noisy_read(badworld, Random(seed), n, common_error=common)
        correlated_rows.append([seed, badestimate ^ truth])
    n_by_t = [repetitions(8, p, 0.05 / (t * (t + 1))) for t in range(1, 9)]
    multi_rows = []
    for seed in range(64):
        changes, noise = Random(100000 + seed), Random(200000 + seed)
        previous = 0
        for t, count in enumerate(n_by_t, 1):
            truth = changes.randrange(256)
            world = World(3, truth, changes.randrange(256))
            estimate, votes = noisy_read(world, noise, count)
            # 每次定期窗口都重新审计，没有收到变化位置或真值标签。
            before = 8 - bits(previous ^ truth)
            world.correction = lambda x, u=estimate: (u >> x) & 1
            after = sum(world.execute(x, 1) == 1 for x in range(8))
            multi_rows.append([seed, t, truth, previous, estimate, count, before, after, votes])
            previous = estimate
    tail = majority_error(n, p)
    return {"summary": {"drift_transitions": checked,
            "no_recheck_wrong": checked,
            "four_point_detected": sum(r[1] for r in old_rows),
            "four_point_undetected": sum(r[2] for r in old_rows),
            "eight_point_recovered": sum(r[3] for r in old_rows),
            "noise_seeds": 4096, "noise_p": p, "repeats": n,
            "noise_failed_audits": sum(bool(r[3]) for r in noise_rows),
            "noise_majority_bit_error_exact": tail,
            "noise_any_error_exact": 1 - (1 - tail) ** 8,
            "noise_any_error_union_bound": min(1, 8 * tail),
            "correlated_failed_audits": sum(bool(r[1]) for r in correlated_rows),
            "multi_sequences": 64, "multi_windows": len(multi_rows),
            "multi_failed_windows": sum(r[7] != 8 for r in multi_rows),
            "multi_sequences_with_error": len({r[0] for r in multi_rows if r[7] != 8}),
            "multi_repeats_by_t": n_by_t,
            "multi_allocated_risk_sum": sum(0.05 / (t * (t + 1)) for t in range(1, 9)),
            "multi_actual_union_bound": sum(8 * majority_error(count, p) for count in n_by_t)},
            "transition_encoding": {"kind": "lossless_xor_factorization", "new": "old XOR delta",
              "old_values": list(range(256)), "delta_columns": ["delta", "detected_in_four", "error_after_patch_four"],
              "delta_rows": delta_rows, "old_columns": ["old", "detected", "missed", "recovered_all"],
              "old_rows": old_rows, "audit_input_order": order},
            "noise_columns": ["seed", "truth", "ones_per_input", "error_mask"], "noise_rows": noise_rows,
            "correlated_columns": ["seed", "error_mask"], "correlated_rows": correlated_rows,
            "multi_columns": ["seed", "window", "truth", "prior", "adopted", "n", "before_of_8",
                              "after_of_8", "ones_per_input"], "multi_rows": multi_rows}


def run_all():
    return {"M8": m8(), "M9": m9(), "M10": m10()}
