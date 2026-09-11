"""主实验与反证。故障标签/目标函数仅在本评估层使用。"""
from collections import Counter
from dataclasses import asdict, replace
from itertools import combinations, product
from .synthesis import catalogue, compile_expr, evaluate, source, synthesize
from .recovery import (Cell, SLOTS, Ballot, Context, audit, digest, probe,
                       quorum, recover)

INITIAL = (-3, -1, 0, 2, 4)
VALIDATION = (-5, 1, 3, 6)
FUTURE = tuple(x for x in range(-32, 33) if x not in INITIAL + VALIDATION)


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def group():
    return [Cell('cell-' + str(i)) for i in range(4)]


def healthy(cells):
    return all(all(audit(probe(c)).values()) for c in cells)


def m17():
    rows, traces, counts = [], {}, Counter()
    for mode, damaged, mask in product(('silent', 'exception'), range(4), range(1, 64)):
        cells = group()
        originals = {(c.name, s): c.functions[s] for c in cells for s in SLOTS}
        target = cells[damaged]
        instance_id = id(target)
        target.fault(mask, mode)
        try:
            own_verdict = target.call('audit', probe(target))
            self_reported_healthy = all(own_verdict.values())
        except Exception:
            self_reported_healthy = None
        result = recover(cells)
        actual = {(r['subject'], r['slot']) for r in result['changes']}
        expected = {(target.name, s) for i, s in enumerate(SLOTS) if mask & (1 << i)}
        wrong_changes = actual - expected
        missed = expected - actual
        identity_kept = id(target) == instance_id
        unaffected_kept = all(c.functions[s] is originals[c.name, s]
                              for c in cells for s in SLOTS if (c.name, s) not in expected)
        future_checks = [c.decide(x) == x for c in cells for x in range(-21, 22)]
        passed = (not missed and not wrong_changes and identity_kept and unaffected_kept
                  and all(future_checks) and all(all(v.values()) for v in result['behaviour_after'].values()))
        # 结果总数不是检验前固定成成功；任何失败保留在行中并阻止强主张。
        counts['cases'] += 1
        counts['recovered'] += passed
        counts['mispatched_slots'] += len(wrong_changes)
        counts['missed_slots'] += len(missed)
        counts['future_cases'] += len(future_checks)
        counts['future_correct'] += sum(future_checks)
        counts['self_reported_healthy_despite_fault'] += self_reported_healthy is True
        rows.append({'mode': mode, 'damaged_cell': damaged, 'fault_mask': mask,
                     'passed': passed, 'self_reported_healthy': self_reported_healthy,
                     'instance_preserved': identity_kept, 'unaffected_bindings_preserved': unaffected_kept,
                     'future_correct': sum(future_checks), 'changes': result['changes'],
                     'unresolved': result['unresolved'], 'calls': result['calls']})
        if mask == 63 and damaged == 0:
            traces[mode] = result
    normal = group()
    normal_result = recover(normal)
    normal_pass = not normal_result['changes'] and healthy(normal)
    return {'summary': dict(counts, normal_unchanged=normal_pass, max_faulty_cells=1),
            'rows': rows, 'full_examples': traces}


def targets():
    """这份表只由评估器使用。合成器看不到名字、参数和函数体。"""
    tasks = []
    for c in (-2, -1, 0, 1):
        tasks.append(('square_plus_' + str(c), lambda x, c=c: x*x+c))
    for c in (0, 1, 2, 3):
        tasks.append(('absolute_shift_' + str(c), lambda x, c=c: abs(x-c)))
    for c in (-2, -1, 1, 2):
        tasks.append(('parity_linear_' + str(c), lambda x, c=c: x%2+c*x))
    for c in (-2, -1, 0, 1):
        tasks.append(('half_plus_' + str(c), lambda x, c=c: x//2+c))
    for c in (-1, 0, 1, 2):
        tasks.append(('signed_square_' + str(c), lambda x, c=c: x*abs(x)+c))
    for c in (0, 1, 2, 3):
        tasks.append(('shifted_square_' + str(c), lambda x, c=c: (x-c)*(x-c)))
    return tasks


def learn(cell, get_value):
    """真实接口：只通过给定点的反馈合成。未见集不进入本函数。"""
    query_trace = []
    def observe(x):
        value = get_value(x)
        query_trace.append([x, value])
        return value
    evidence = {x: observe(x) for x in INITIAL}
    logs, found = [], None
    for round_id in range(5):
        answer = cell.infer(tuple(evidence.items()), round_id)
        candidate = answer.get('candidate')
        if answer.get('status') != 'fit' or candidate is None:
            logs.append({'status': answer.get('status'), 'attempts': answer.get('attempts', 0)})
            return {'accepted': False, 'rounds': logs, 'observations': list(evidence.items()),
                    'query_trace': query_trace, 'oracle_calls': len(query_trace)}
        program = compile_expr(candidate.expression)
        checks = [(x, observe(x)) for x in VALIDATION]
        failures = [x for x, y in checks if program(x) != y]
        logs.append({'source': program.source, 'expression': candidate.expression,
                     'nodes': candidate.nodes, 'attempts': candidate.attempt,
                     'validation_failures': failures,
                     'catalogue_attempts': answer['shared_catalogue_attempts'],
                     'catalogue_signatures': answer['shared_catalogue_signatures']})
        if cell.call('validate', program, tuple(checks)):
            if cell.deploy(program, tuple(evidence.items()) + tuple(checks)):
                found = candidate
                break
        if not failures:
            break
        x = failures[0]
        evidence[x] = observe(x)
    return {'accepted': found is not None, 'rounds': logs, 'observations': list(evidence.items()),
            'source': cell.program.source if found else None,
            'expression': found.expression if found else None,
            'query_trace': query_trace, 'oracle_calls': len(query_trace)}


def history_comparison(evidence, get_value):
    """同一稳定任务上的信息对照。存量观察取得成本不被算作免费。"""
    saved = tuple(tuple(pair) for pair in evidence)
    archived = synthesize(saved)
    # 没有自身历史也不获取新观察时，接口没有许可猜测一个程序。
    empty_status = 'insufficient_evidence'
    measured = tuple((x, get_value(x)) for x, _ in saved)
    repeated = synthesize(measured)
    a, b = archived['candidate'], repeated['candidate']
    equal = (a.expression if a else None) == (b.expression if b else None)
    return {'no_history_no_probe': empty_status,
            'history_existing_observations': len(saved),
            'history_additional_calls': 0, 'remeasure_additional_calls': len(measured),
            'remeasured_observations': measured, 'same_program': equal,
            'note': '对照仅比较合成输入的恢复；存量证据的原始获取和采用验证仍有成本。'}


def m18():
    rows, integration, counts = [], [], Counter()
    for name, fn in targets():
        cell = Cell('subject')
        report = learn(cell, fn)
        results = [cell.decide(x) == fn(x) for x in FUTURE]
        fixed = [(a, b) for a in range(-4, 5) for b in range(-4, 5)
                 if all(a*x+b == fn(x) for x in INITIAL + VALIDATION)]
        # 同信息JSON日志重新提供观测，不导入目标实现或递归复查内容。
        import json
        final_observations = json.loads(json.dumps(report['observations']))
        plain = synthesize(tuple(tuple(pair) for pair in final_observations))
        plain_expr = plain['candidate'].expression if plain['candidate'] else None
        same = plain_expr == report['expression'] if report['accepted'] else True
        counts['tasks'] += 1
        counts['accepted'] += report['accepted']
        counts['all_future_correct'] += report['accepted'] and all(results)
        counts['future_cases'] += len(results)
        counts['future_correct'] += sum(results) if report['accepted'] else 0
        counts['fixed_affine_fits'] += bool(fixed)
        counts['plain_log_equal'] += same
        memory = history_comparison(report['observations'], fn)
        counts['remeasure_equal'] += memory['same_program']
        counts['remeasure_additional_calls'] += memory['remeasure_additional_calls']
        counts['history_observation_count'] += memory['history_existing_observations']
        counts['learning_oracle_calls'] += report['oracle_calls']
        rows.append({'task': name, **report, 'future_x': FUTURE,
                     'future_expected': [fn(x) for x in FUTURE],
                     'future_actual': [cell.decide(x) for x in FUTURE] if report['accepted'] else None,
                     'future_correct': sum(results) if report['accepted'] else 0,
                     'fixed_affine_candidates': fixed, 'plain_log_equal': same,
                     'history_comparison': memory})
        for damaged in range(4):
            cells = group()
            cells[damaged].fault(63, 'silent')
            recovered = recover(cells)
            repaired = learn(cells[damaged], fn)
            future = [cells[damaged].decide(x) == fn(x) for x in FUTURE]
            passed = (len(recovered['changes']) == 6 and repaired['accepted'] and all(future))
            integration.append({'task': name, 'damaged_cell': damaged,
                                'repaired_slots': [c['slot'] for c in recovered['changes']],
                                'source': repaired.get('source'), 'accepted': repaired['accepted'],
                                'future_correct': sum(future) if repaired['accepted'] else 0, 'passed': passed})
    counts['integration_cases'] = len(integration)
    counts['integration_passed'] = sum(r['passed'] for r in integration)
    counts['holdout_inputs_per_task'] = len(FUTURE)
    return {'summary': dict(counts), 'rows': rows, 'integration': integration,
            'cache': catalogue.cache_info()._asdict(),
            'cost_note': '相同输入集共享预计算目录；attempts是独立有界枚举中的发现序号，不是实际总CPU成本。'}


def m19():
    ctx = Context('cell-0', 3, 'evidence-A', 'candidate-A', 'audit')
    registry = tuple('cell-' + str(i) for i in range(4))
    good = (Ballot('cell-1', ctx, True), Ballot('cell-2', ctx, True))
    attacks = {}
    attacks['correct_fresh_two_sources'] = good
    attacks['duplicate_single_source'] = (good[0],) * 20
    attacks['self_vote_plus_one'] = (Ballot('cell-0', ctx, True), good[0])
    attacks['old_target_version'] = tuple(replace(b, context=replace(ctx, version=2)) for b in good)
    attacks['different_evidence'] = tuple(replace(b, context=replace(ctx, evidence='evidence-B')) for b in good)
    attacks['different_candidate'] = tuple(replace(b, context=replace(ctx, candidate='candidate-B')) for b in good)
    attacks['different_slot'] = tuple(replace(b, context=replace(ctx, slot='generate')) for b in good)
    attacks['invented_source'] = (Ballot('clone-1', ctx, True), Ballot('clone-2', ctx, True))
    attacks['equivocation'] = good + (Ballot('cell-2', ctx, False),)
    rows = [{'case': name, 'contextual_accepts': bool(quorum(ballots, ctx, registry)),
             'naive_accepts': sum(b.approved for b in ballots) >= 2,
             'ballots': [asdict(b) for b in ballots]} for name, ballots in attacks.items()]
    # 穷举不同来源的投票值。在其他三票中最多一个任意错误的条件下，二票多数正确。
    majority_rows = []
    for truth in (False, True):
        for faulty in (None, 1, 2, 3):
            for false_vote in (False, True):
                ballots = tuple(Ballot('cell-' + str(i), ctx, false_vote if i == faulty else truth)
                                for i in (1, 2, 3))
                decision = bool(quorum(ballots, ctx, registry))
                majority_rows.append([truth, faulty, false_vote, decision, decision == truth])
    # 两个说谎者可把错误的candidate变成“通过”；这是明确的超出故障预算反例。
    bad_votes = (Ballot('cell-1', ctx, True), Ballot('cell-2', ctx, True), Ballot('cell-3', ctx, False))
    two_faulty_unsound = bool(quorum(bad_votes, ctx, registry))
    common = group()
    for c in common: c.fault(63, 'silent')
    common_result = recover(common)
    common_recovered = healthy(common)
    crashed = group()
    for c in crashed: c.fault(63, 'exception')
    crash_result = recover(crashed)
    # 有限数据相同而未见分支不同的真正可执行函数，非口头“可能出错”。
    baseline = lambda x: x*x
    hidden = lambda x: x*x + int(x == 17)
    measured = INITIAL + VALIDATION
    equal_seen = all(baseline(x) == hidden(x) for x in measured)
    cell = Cell('latent-target')
    latent_fit = learn(cell, hidden)
    latent_errors = [x for x in FUTURE if cell.decide(x) != hidden(x)] if latent_fit['accepted'] else None
    limited = synthesize(tuple((x, x*x) for x in INITIAL), max_nodes=1, budget=7)
    # 错误参照可让全体健全单元一致采用错误目标；安装器破坏不受票决保护。
    wrong_spec = Cell('wrong-reference')
    wrong_spec_fit = learn(wrong_spec, lambda x: x+1)
    wrong_reference_errors = sum(wrong_spec.decide(x) != x for x in FUTURE)
    tampered = Cell('bad-installer')
    tampered.program = compile_expr(('c', 42))
    installation_errors = sum(tampered.decide(x) != x for x in FUTURE)
    return {'summary': {
                'context_cases': len(rows),
                'invalid_contexts_rejected': sum(not r['contextual_accepts'] for r in rows[1:]),
                'naive_invalid_accepts': sum(r['naive_accepts'] for r in rows[1:]),
                'single_fault_majority_cases': len(majority_rows),
                'single_fault_majority_correct': sum(r[-1] for r in majority_rows),
                'two_faulty_false_approval': two_faulty_unsound,
                'all_corrupt_recovered': common_recovered,
                'all_crashed_recovered': healthy(crashed),
                'latent_identical_seen': equal_seen,
                'latent_accepted': latent_fit['accepted'], 'latent_future_errors': latent_errors,
                'resource_limited_status': limited['status'],
                'wrong_reference_accepted': wrong_spec_fit['accepted'],
                'wrong_reference_future_errors': wrong_reference_errors,
                'tampered_installation_future_errors': installation_errors},
            'contexts': rows, 'majority_rows': majority_rows,
            'common_failure_trace': common_result, 'crash_trace': crash_result,
            'latent_trace': latent_fit}


def run_all():
    return {'M17': m17(), 'M18': m18(), 'M19': m19()}
