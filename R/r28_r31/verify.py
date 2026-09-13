"""Independent arithmetic interpreter for R31 archives; no learner import.
Same declared finite world/PRNG is trusted, not an independent physical world.
"""
from math import sqrt, isclose
from statistics import mean
import json

from r4_r7.search import make_problem
from .space import freeze, digest


TASK_VARS = ('info', 'price', 'spread', 'order')
META_VARS = ('mean', 'uncert', 'visits', 'gap')


def evaluate(tree, values, task=False):
    if type(tree) is int:
        return tree * 256 if task else float(tree)
    if isinstance(tree, str):
        return values[(TASK_VARS if task else META_VARS).index(tree)]
    op, left, right = tree
    a, b = evaluate(left, values, task), evaluate(right, values, task)
    if op == '+': value = a + b
    elif op == '-': value = a - b
    elif op == '*': value = a * b // 256 if task else a * b
    elif op == '/': value = a * 256 // (abs(b) + 1) if task else a / (abs(b) + .001)
    else: raise ValueError('invalid opcode')
    bound = 10 ** 9 if task else 10 ** 6
    return min(bound, max(-bound, value))


def ast_size(t):
    return 1 if isinstance(t, (int, str)) else 1 + ast_size(t[1]) + ast_size(t[2])


def ast_text(t):
    return str(t) if isinstance(t, (int, str)) else '(' + ast_text(t[1]) + t[0] + ast_text(t[2]) + ')'


def diagnostic(problem, inferred, program):
    masks, prices, count = problem['masks'], problem['prices'], problem['count']
    remaining = (1 << count) - 1
    available = list(range(len(masks)))
    trace = []
    total = 0
    while remaining.bit_count() > 1 and available:
        choices = []
        n = remaining.bit_count()
        for query in available:
            sizes = [(m & remaining).bit_count() for m in masks[query]]
            info = (n * n - sum(x * x for x in sizes)) * 1024 // (n * n)
            features = (info, prices[query] * 128, sum(x > 0 for x in sizes) * 128, query * 16)
            if info > 0:
                choices.append((evaluate(program, features, True), -query, query, features))
        if not choices:
            break
        _, _, query, features = max(choices)
        reply = next(j for j, mask in enumerate(masks[query]) if mask & (1 << inferred))
        after = remaining & masks[query][reply]
        trace.append({'query': query, 'value': reply, 'before': remaining, 'after': after,
                      'features': features, 'price': prices[query]})
        remaining = after
        total += prices[query]
        available.remove(query)
    price = total if remaining.bit_count() == 1 else total + 1000
    return price, remaining, trace


def reference_intervention(bundle, tasks, block):
    cache = {}
    def task_loss(arm, j):
        key = (arm, j)
        if key not in cache:
            p, h = block[j]
            price, rem, tr = diagnostic(p, h, tasks[arm])
            value = price / (9 * len(p['masks'])) if rem.bit_count() == 1 else 1.0
            cache[key] = value, tuple((r['query'], r['value'], r['price']) for r in tr)
        return cache[key]
    values = [[] for _ in tasks]
    requests = []
    for step in range(12):
        if step < len(tasks):
            chosen = step
        else:
            means = [sum(v) / len(v) for v in values]
            minimum = min(means)
            scores = []
            for row, m in zip(values, means):
                variance = sum((v - m) ** 2 for v in row) / max(1, len(row) - 1)
                u = bundle['scale'] * sqrt((variance + .01) / len(row))
                scores.append(evaluate(bundle['ast'], (m, u, len(row) / 12, m - minimum)))
            chosen = min(range(len(tasks)), key=lambda i: (scores[i], i))
        index = len(values[chosen])
        loss, _ = task_loss(chosen, index % 4)
        values[chosen].append(loss)
        requests.append((chosen, index, loss))
    means = [sum(v) / len(v) for v in values]
    best = min(range(len(tasks)), key=lambda i: (means[i], ast_size(tasks[i]), ast_text(tasks[i])))
    tests = [task_loss(best, j) for j in (4, 5)]
    return {'loss': mean(x[0] for x in tests), 'signature': tuple(x[1] for x in tests),
            'task': best, 'requests': tuple(requests)}


def equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return isclose(a, b, abs_tol=1e-12, rel_tol=1e-12)
    return a == b


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_episode(result, evaluate_holdouts=True):
    records = result['ledger']
    bodies = [json.loads(r['body']) for r in records]
    invalid = set()
    actual_queries = actual_price = 0
    checked = 0
    blocks = {}
    current_task = 0
    for i, (record, body) in enumerate(zip(records, bodies)):
        require(record['seq'] == i, 'nonsequential history')
        for kind in ('refs', 'deps'):
            require(len(set(record[kind])) == len(record[kind]), 'duplicate edges')
            require(all(type(k) is int and 0 <= k < i for k in record[kind]), 'future edge')
        if record['kind'] == 'revocation':
            invalid.add(body['root'])
        if any(k in invalid for k in record['deps']):
            invalid.add(i)
        if record['kind'] == 'R30_actual_task_binding':
            current_task = freeze(body['after'])
        if record['kind'] == 'R30_diagnostic_intention':
            require(freeze(body['program']) == freeze(current_task), 'solver binding not used')
        if record['kind'] == 'R30_diagnostic_observation':
            intent = bodies[body['intention']]
            price, remaining, trace = diagnostic(intent['problem'], body['inferred_mechanism'], intent['program'])
            require(equal(trace, body['transcript']), 'own query transcript mismatch')
            require(remaining == 1 << body['inferred_mechanism'] and price == body['price'], 'inference mismatch')
            actual_queries += len(trace)
            actual_price += price
        if record['kind'] == 'R30_observed_block':
            blocks[i] = [(row['problem'], row['inferred']) for row in body['cases']]
    # Revocation can reach earlier records: do a fresh full topological pass.
    invalid = {bodies[i]['root'] for i, r in enumerate(records) if r['kind'] == 'revocation'}
    for i, r in enumerate(records):
        if any(p in invalid for p in r['deps']):
            invalid.add(i)
    require(invalid == set(result['invalid']), 'revocation mismatch')
    require(actual_queries == result['actual_cost']['actual_queries'], 'actual query count')
    require(actual_price == result['actual_cost']['paid_probe_cost'], 'actual price count')
    from random import Random
    for round_ in result['rounds']:
        proposal = bodies[round_['proposal_record']]
        check = bodies[round_['check_record']]
        pool = proposal['pool']
        bundle_map = {b['key']: b for b in pool}
        require(all(digest([b['ast'], b['scale']]) == b['key'] for b in pool), 'bundle identity')
        tasks = proposal['tasks']
        histories = [blocks[k] for k in proposal['history_records']]
        fresh_ids = [k for k in records[round_['check_record']]['deps'] if k in blocks]
        require(len(fresh_ids) == 4 and all(k > round_['proposal_record'] for k in fresh_ids), 'nonfresh adoption')
        fresh = [blocks[k] for k in fresh_ids]
        for field, data in [('proposal_interventions', histories), ('adoption_interventions', fresh)]:
            for cell in round_[field]:
                reference = reference_intervention(bundle_map[cell['bundle']], tasks, data[cell['block']])
                require(equal(reference, {k: cell[k] for k in reference}), 'intervention arithmetic mismatch')
                checked += 1
        if evaluate_holdouts:
            generation = round_['generation']
            test_blocks = []
            for j in range(6):
                rng = Random(result['seed'] * 100000 + 5000 + generation * 20 + j)
                block = []
                for _ in range(6):
                    p, h = make_problem(rng.randrange(1 << 50), n=16, nq=12)
                    block.append(({'masks': p.masks, 'prices': p.prices, 'count': p.count}, h))
                test_blocks.append(block)
            choices = {'parent': proposal['parent'], 'child': round_['child']}
            for name, branch in proposal['branches'].items():
                choices[name] = branch['candidate'] if check['checks'][name]['accepted'] else proposal['parent']
            for name, bundle in choices.items():
                values = [reference_intervention(bundle, tasks, block)['loss'] for block in test_blocks]
                require(equal(values, round_['evaluation_only']['blocks'][name]), 'heldout arithmetic mismatch')
                checked += len(values)
        for name, branch in proposal['branches'].items():
            values = check['checks'][name]
            should = (branch['candidate']['key'] != proposal['parent']['key'] and
                      mean(values['old']) - mean(values['new']) > .002)
            require(should == values['accepted'], 'adoption gate mismatch')
        m = round_['evaluation_only']['means']
        delta, gp, gi = m['parent'] - m['child'], m['previous'] - m['child'], m['initial'] - m['child']
        strict = (round_['generation'] > 0 and round_['previous_adopted'] and round_['adopted']
                  and min(delta, gp, gi) > 1e-12)
        require(strict == round_['strict_empirical_link'], 'recursive criterion mismatch')
    return {'own_queries': actual_queries, 'own_query_price': actual_price,
            'intervention_and_test_checks': checked, 'ledger_records': len(records), 'passed': True}
