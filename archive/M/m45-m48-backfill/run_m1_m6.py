"""穷举 M1–M6；亲自执行才生成结果。仅写本仓库 results/。"""
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
import gzip
import json
import platform
from library_experiments import *

ROOT = Path(__file__).resolve().parent

def digest(obj):
    return sha256(encode(obj).encode()).hexdigest()


def save_result(stem, data):
    data['python'] = platform.python_version()
    # 显式限定本轮依赖；仓库原有 run_m0.py 不应改变本轮结果摘要。
    sources = ('library_experiments.py', 'run_m1_m6.py', 'run_m7.py')
    data['source_sha256'] = {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}
    raw = (encode(data) + '\n').encode()
    h = sha256(raw).hexdigest()
    out = ROOT / 'results'
    (out / 'runs').mkdir(parents=True, exist_ok=True)
    packed = gzip.compress(raw, mtime=0)
    archive = out / 'runs' / (h + '.json.gz')
    if archive.exists():
        require(gzip.decompress(archive.read_bytes()) == raw, 'archive collision')
    else:
        archive.write_bytes(packed)
    summary = {'archive': str(archive.relative_to(ROOT)), 'sha256_uncompressed': h,
               'python': data['python'], 'summary': data['summary'], 'source_sha256': data['source_sha256']}
    (out / (stem + '_summary.json')).write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2)+'\n')
    print(stem, json.dumps(data['summary'], ensure_ascii=False, sort_keys=True))
    print('archive', h, 'compressed bytes', len(packed))
    return data, h


def bound_check():
    # 真世界0的每个约束子集，线性族其他非空证据类是其平移。
    sets = [ALL] * (1 << 16)
    best_repair, best_identify = 99, 99
    rh, ih = Counter(), Counter()
    for s in range(1 << 16):
        if s:
            bit = s & -s
            q = bit.bit_length() - 1
            sets[s] = sets[s ^ bit] & (ALL ^ ONES[q])
        H, n = sets[s], s.bit_count()
        if resolved(H, 'repair'):
            rh[n] += 1
            best_repair = min(best_repair, n)
        if resolved(H, 'identify'):
            ih[n] += 1
            best_identify = min(best_identify, n)
    return {'subsets': len(sets), 'repair_minimum': best_repair, 'identify_minimum': best_identify,
            'repair_count_by_subset_size': dict(rh), 'identify_count_by_subset_size': dict(ih)}


def main():
    rows, diagnostics, trace_example = [], [], None
    comparisons = Counter()
    for i, theta in enumerate(PARAMS):
        world = World(theta)
        active = diagnose(world.observe, trace=True)
        plain = diagnose(world.observe, backend='plain', trace=True)
        fast = diagnose(world.observe)
        passive = diagnose(world.observe, policy='passive')
        full = diagnose(world.observe, purpose='identify')
        require(active == plain, 'same-information log differs')
        require(active['H'] == fast['H'] and active['history'] == fast['history'], 'tracing changes diagnosis')
        require(active['status'] == 'sufficient', 'active unresolved')
        u = active['choices'][0]
        adopted = adopt(world, u)
        ok = adopted['accepted'] and all(adopted['challenge'])
        require(ok and u == repair(theta) and ids(full['H']) == [i], 'main-family failure')
        comparisons['all_cases_repaired'] += ok
        comparisons['nonzero_corrections'] += u != 0
        comparisons['no_change_needed'] += u == 0
        comparisons['plain_equal'] += active == plain
        comparisons['passive_unresolved'] += passive['status'] == 'unresolved'
        comparisons['identify_correct'] += ids(full['H']) == [i]
        comparisons['validation_regressions'] += adopted['regressions']
        diagnostics.append(active['H'])
        rows.append({'world': i, 'theta': theta, 'u': u, 'H_count': active['H'].bit_count(),
                     'active_cost': active['cost'], 'full_cost': full['cost'],
                     'passive_candidates': passive['H'].bit_count(), 'history': active['history'],
                     'full_history': full['history'], 'adoption': adopted})
        if i == 109:
            trace_example = active
    random_rows, random_hist = [], Counter()
    for seed in range(64):
        transcripts, costs, correct = [], [], 0
        for i, theta in enumerate(PARAMS):
            d = diagnose(World(theta).observe, policy='random', seed=seed)
            cost = d['cost']['interactions']
            costs.append(cost)
            random_hist[cost] += 1
            correct += d['status'] == 'sufficient' and d['choices'] == [repair(theta)]
            transcripts.append([i, d['history'], d['choices'], d['H']])
        require(correct == 256, 'random baseline unresolved or wrong')
        random_rows.append({'seed': seed, 'correct': correct, 'costs_in_world_order': costs,
                            'transcript_sha256': digest(transcripts)})
    # M4：标签不可信可产生一致但错误的归因。
    swapped, ood_failed, validation_rolled_back = 0, 0, 0
    for i, theta in enumerate(PARAMS):
        world = World(theta)
        def wrong_label(q):
            m, x = QUERIES[q]
            swapped_m = (m & 4) | ((m & 1) << 1) | ((m & 2) >> 1)
            return world.execute(x, 0, swapped_m)
        d = diagnose(wrong_label, purpose='identify')
        swapped += ids(d['H']) != [i]
        nonlinear = World(theta, nonlinear=True)
        d = diagnose(nonlinear.observe)
        a = adopt(nonlinear, d['choices'][0])
        ood_failed += a['accepted'] and not all(a['challenge'])
        payload = World(theta, payload_fault=True)
        d = diagnose(payload.observe)
        a = adopt(payload, d['choices'][0])
        validation_rolled_back += not a['accepted'] and payload.correction == 0
    # M5：共同旧知识由完整识别生成，真参数只在评估侧比对。
    changes, change_counts = [], Counter()
    for i, theta in enumerate(PARAMS):
        known = diagnose(World(theta).observe, purpose='identify')['H']
        for component in range(4):
            initial = lift(known, (component,))
            for delta in (1, 2, 3):
                new = list(theta)
                new[component] ^= delta
                new = tuple(new)
                world = World(new)
                aware_r = diagnose(world.observe, initial=initial, prefix=())
                aware_i = diagnose(world.observe, initial=initial, prefix=(), purpose='identify')
                reset_r = diagnose(world.observe, prefix=())
                reset_i = diagnose(world.observe, prefix=(), purpose='identify')
                blind = choices(known)[0]
                merged = known
                for q in PASSIVE:
                    merged = filter_H(merged, q, world.observe(q))
                require(aware_r['choices'] == [repair(new)] and ids(aware_i['H']) == [PARAMS.index(new)], 'transition failure')
                change_counts['aware_repair_correct'] += 1
                change_counts['aware_identify_correct'] += 1
                change_counts['blind_repair_wrong'] += blind != repair(new)
                change_counts['blind_identify_wrong'] += True
                change_counts['merge_inconsistent'] += merged == 0
                cr, ci = aware_r['cost']['interactions'], aware_i['cost']['interactions']
                rr, ri = reset_r['cost']['interactions'], reset_i['cost']['interactions']
                for k, v in [('aware_repair_queries', cr), ('aware_identify_queries', ci), ('reset_repair_queries', rr), ('reset_identify_queries', ri)]:
                    change_counts[k] += v
                changes.append([i, component, delta, PARAMS.index(new), cr, ci, rr, ri, blind != repair(new), merged == 0])
    bounds = bound_check()
    summary = {
        'M1_M3': dict(comparisons), 'worlds': 256,
        'active_query_histogram': dict(Counter(r['active_cost']['interactions'] for r in rows)),
        'identify_query_histogram': dict(Counter(r['full_cost']['interactions'] for r in rows)),
        'active_remaining_hypotheses': sorted(set(r['H_count'] for r in rows)),
        'random_runs': 64*256, 'random_query_histogram': dict(sorted(random_hist.items())),
        'random_mean_queries': sum(k*v for k,v in random_hist.items()) / (64*256),
        'M4': {'swapped_provenance_wrong_attribution': swapped, 'nonlinear_accepted_but_challenge_failed': ood_failed,
               'payload_fault_validation_rollback': validation_rolled_back},
        'M5': {'transitions': len(changes), **dict(change_counts)}, 'M6': bounds
    }
    data = {'summary': summary, 'world_rows': rows, 'random_seed_rows': random_rows,
            'transition_columns': ['old_world','component','delta','new_world','aware_r','aware_i','reset_r','reset_i','blind_wrong','merged_empty'],
            'transition_rows': changes, 'automatic_trace_example': trace_example,
            'protocol_commit': 'c877f87170664c586cb069b6c685dd4ec223677d',
            'command': 'python3 run_m1_m6.py', 'public_precompute_predictions': 4096}
    return save_result('m1_m6', data)

if __name__ == '__main__':
    main()
