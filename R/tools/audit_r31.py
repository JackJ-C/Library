"""R31 post-freeze read-only linkage audit. Never changes learner or raw data.
Run from R/: python tools/audit_r31.py. Uses the frozen arithmetic reference,
not the learner. Adds links, summaries, ranking and instrumented cost checks.
The generator, persisted port observations, and Python runtime remain trusted.
"""
from collections import Counter
from hashlib import sha256
import json
import lzma
from math import isfinite, sqrt, log
from pathlib import Path
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from r28_r31.verify import (verify_episode, reference_intervention, diagnostic,
                            evaluate, ast_size, equal, require)
from r28_r31.space import freeze, digest

INITIAL = {'ast': ['-', 'mean', 'uncert'], 'scale': 1.0,
           'key': digest([['-', 'mean', 'uncert'], 1.0])}
BRANCHES = ('primary', 'graph', 'raw', 'shuffled', 'collapsed', 'previous', 'initial')


def finite(x):
    if isinstance(x, float):
        require(isfinite(x), 'nonfinite number')
    elif isinstance(x, dict):
        for v in x.values(): finite(v)
    elif isinstance(x, (list, tuple)):
        for v in x: finite(v)


def same(a, b, label):
    require(equal(a, b), label)


def partition(rows):
    seen = {}
    return [seen.setdefault(freeze(r), len(seen)) for r in rows]


def geometry(rows, mode):
    rows = list(rows)
    if mode == 'shuffled': rows = rows[1:] + rows[:1]
    if mode == 'collapsed': rows = [rows[0]] * len(rows)
    return partition(rows), [[mean(a != b for a, b in zip(x, y))
                              for y in rows] for x in rows]


def select_reference(parent, proposer, pool, cells, history_n, rows, mode):
    pilots_n = min(3, history_n - 1)
    dev = list(range(pilots_n, history_n))
    pilots = [[cells[(b['key'], j)]['loss'] for j in range(pilots_n)] for b in pool]
    averages = [mean(row) for row in pilots]
    minimum = min(averages)
    groups, distances = geometry(rows, mode)
    selected, selected_groups, rankings = [], set(), []
    operations = 0
    for _ in range(2):
        eligible = [i for i in range(1, len(pool)) if i not in selected]
        if mode != 'raw':
            novel = [i for i in eligible if groups[i] not in selected_groups]
            if novel: eligible = novel
        priorities = []
        for i in eligible:
            variance = mean((x - averages[i]) ** 2 for x in pilots[i])
            uncertainty = sqrt((variance + .0001) / pilots_n)
            if mode != 'raw':
                uncertainty += .025 * min(distances[i][j] for j in [0] + selected)
            features = (averages[i], proposer['scale'] * uncertainty,
                        pilots_n / history_n, averages[i] - minimum)
            value = evaluate(proposer['ast'], features)
            operations += ast_size(proposer['ast'])
            priorities.append((value, ast_size(pool[i]['ast']), pool[i]['key'], i, features))
        winner = min(priorities)[3]
        selected.append(winner); selected_groups.add(groups[winner])
        rankings.append({'eligible': eligible, 'chosen': winner,
                         'priorities': [[p[3], p[0], p[4]] for p in priorities]})
    scores = [(mean(cells[(pool[i]['key'], j)]['loss'] for j in dev),
               0 if i == 0 else 1, ast_size(pool[i]['ast']), pool[i]['key'], i)
              for i in [0] + selected]
    chosen = min(scores)[-1]
    return pool[chosen], {'mode': mode, 'proposer': proposer,
                         'pilot_means': averages, 'shortlist': selected,
                         'proposal': chosen, 'scores': [[x[-1], x[0]] for x in scores],
                         'ranking': rankings, 'logical_full_checks': 2 * len(dev)}, operations


def diagnostic_cost(problem, inferred, program):
    price, remaining, trace = diagnostic(problem, inferred, program)
    available = set(range(len(problem['masks'])))
    features = operations = 0
    for row in trace:
        H = row['before']; n = H.bit_count()
        for q in available:
            counts = [(mask & H).bit_count() for mask in problem['masks'][q]]
            features += len(counts) + 3
            info = (n*n - sum(v*v for v in counts)) * 1024 // (n*n)
            if info > 0: operations += ast_size(program)
        available.remove(row['query'])
    return {'queries': len(trace), 'price': price, 'ast': operations, 'features': features}


def engine_cost(cells, bundle_map, tasks, blocks, requests, extra_ops=0):
    keys = set()
    for cell in cells:
        for arm, index, _ in cell['requests']:
            keys.add((arm, cell['block'], index % 4))
        for index in (4, 5): keys.add((cell['task'], cell['block'], index))
    result = Counter(intervention_requests=requests, interventions_executed=len(cells),
                     intervention_cache_hits=requests-len(cells),
                     task_loss_requests=14*len(cells), task_cache_hits=14*len(cells)-len(keys),
                     loss_requests=12*len(cells),
                     allocation_ast_ops=extra_ops + sum(36*ast_size(bundle_map[c['bundle']]['ast'])
                                                       for c in cells))
    for arm, block_id, index in keys:
        p, h = blocks[block_id][index]
        c = diagnostic_cost(p, h, tasks[arm])
        result.update(simulated_queries=c['queries'], simulated_query_price=c['price'],
                      task_ast_ops=c['ast'], task_feature_ops=c['features'])
    if result["task_cache_hits"] == 0:
        del result["task_cache_hits"]  # frozen Counter never touches this key without a hit
    return dict(result)


def audit_episode(x, run_arithmetic=True):
    finite(x)
    reference = verify_episode(x) if run_arithmetic else None
    records = x['ledger']; bodies = [json.loads(r['body']) for r in records]
    for b in bodies: finite(b)
    require(x['mode'] in ('space', 'raw', 'frozen'), 'method identity')
    require(len(x['rounds']) == 6, 'generation count')
    blocks = {}; actual = Counter()
    for rec, body in zip(records, bodies):
        if rec['kind'] == 'R30_diagnostic_observation':
            intent = bodies[body['intention']]
            actual.update(diagnostic_cost(intent['problem'], body['inferred_mechanism'], intent['program']))
        if rec['kind'] == 'R30_observed_block':
            require(len(body['cases']) == 6, 'block size')
            for row in body['cases']:
                intent, receipt = bodies[row['intention']], bodies[row['receipt']]
                same(row['problem'], intent['problem'], 'block-to-intention problem')
                same(row['inferred'], receipt['inferred_mechanism'], 'block-to-receipt inference')
                same(receipt['intention'], row['intention'], 'paired receipt')
                require(row['intention'] < row['receipt'] < rec['seq'], 'observation chronology')
            blocks[rec['seq']] = [(r['problem'], r['inferred']) for r in body['cases']]
    same(x['actual_cost'], {'feature_ops': actual['features'], 'ast_ops': actual['ast'],
         'simulated_queries': 0, 'actual_queries': actual['queries'],
         'paid_probe_cost': actual['price'], 'full_evaluations': 0}, 'all actual cost fields')
    parent, previous, previous_adopted, current_task = INITIAL, INITIAL, False, 0
    ranking_operations = 0
    for g, r in enumerate(x['rounds']):
        same(r['generation'], g, 'generation order')
        proposal = bodies[r['proposal_record']]; check = bodies[r['check_record']]
        same(proposal['parent'], parent, 'parent lineage')
        same(proposal['previous'], previous, 'previous proposer lineage')
        same(r['parent'], parent, 'round parent')
        same(r['previous_adopted'], previous_adopted, 'actual previous adoption')
        pool = proposal['pool']; tasks = proposal['tasks']; bm = {b['key']: b for b in pool}
        same(pool[0], parent, 'parent in candidate pool')
        require(len(pool) == len(bm) == 8 and len(tasks) == 6, 'frozen candidate counts')
        same(tasks[0], current_task, 'actual incumbent solver')
        hids = proposal['history_records']; histories = [blocks[k] for k in hids]
        require(4 <= len(hids) <= 6 and len(set(hids)) == len(hids), 'history range')
        fresh_ids = [k for k in records[r['check_record']]['deps'] if k in blocks]
        for k in fresh_ids:
            require(min(row['intention'] for row in bodies[k]['cases']) > r['proposal_record'],
                    'queries before proposal freeze')
        fresh = [blocks[k] for k in fresh_ids]
        require(not set(hids) & set(fresh_ids), 'reused adoption block')
        cells = {(c['bundle'], c['block']): c for c in r['proposal_interventions']}
        acells = {(c['bundle'], c['block']): c for c in r['adoption_interventions']}
        require(len(cells) == len(r['proposal_interventions']) and
                len(acells) == len(r['adoption_interventions']), 'duplicate intervention cells')
        # Reconstruct the selected witness coordinates directly from executed cells.
        signatures = [() for _ in pool]; axes = []; splits = []
        for j in range(min(3, len(histories)-1)):
            new = [signatures[i] + (freeze(cells[(b['key'], j)]['signature']),)
                   for i, b in enumerate(pool)]
            before, after = len(set(signatures)), len(set(new))
            if j == 0 or after > before:
                axes.append(j); signatures = new
                if after > before: splits.append([j, before, after])
        s = proposal['space']; same(s, r['space'], 'space public copy')
        same(s['axes'], axes, 'witness axes'); same(s['splits'], splits, 'witness splits')
        same(s['dimension'], len(axes), 'coordinate count')
        same(s['groups'], partition(signatures), 'space classes')
        same(s['classes'], len(set(signatures)), 'class count')
        require(len(s['coordinate_records']) == len(axes), 'coordinate records')
        for j, rid in zip(axes, s['coordinate_records']):
            b = bodies[rid]
            same(b['axis'], j, 'coordinate index')
            same(b['bundle_ids'], [p['key'] for p in pool], 'intervention association')
            same(records[rid]['deps'], [hids[j]], 'coordinate support')
            same(b['responses'], [{k: cells[(p['key'], j)][k]
                 for k in ('loss', 'signature', 'task', 'requests')} for p in pool], 'coordinate response')
        same(records[s['space_record']]['deps'], s['coordinate_records'], 'space support closure')
        same(bodies[s['space_record']]['coordinates'], s['coordinate_records'], 'graph reconstruction edges')
        require(set(proposal['branches']) == set(BRANCHES), 'branch coverage')
        ops = 0
        for name in BRANCHES:
            if name == 'primary':
                proposer = INITIAL if x['mode'] == 'frozen' else parent
                mode = 'raw' if x['mode'] == 'raw' else 'space'
            else:
                proposer = previous if name == 'previous' else INITIAL if name == 'initial' else parent
                mode = 'space' if name in ('previous', 'initial') else name
            candidate, selection, count = select_reference(parent, proposer, pool, cells,
                                                             len(hids), signatures, mode)
            ops += count
            same(proposal['branches'][name], {'candidate': candidate, 'selection': selection}, 'shortlist '+name)
            values = check['checks'][name]
            old = [acells[(parent['key'], j)]['loss'] for j in range(4)]
            new = [acells[(candidate['key'], j)]['loss'] for j in range(4)]
            same(values['old'], old, 'adoption old-to-execution '+name)
            same(values['new'], new, 'adoption new-to-execution '+name)
            gain = mean(old)-mean(new)
            same(values['accepted'], candidate['key'] != parent['key'] and gain > .002, 'adoption truth '+name)
            cert = {'scope': 'exact observed finite adoption bank, not future distribution',
                    'independent_blocks': 4, 'empirical_gain': gain,
                    'hoeffding_single_comparison_lcb': gain-sqrt(2*log(2/.05)/4),
                    'distribution_certificate': 'UNKNOWN'}
            same(values['certificate'], cert, 'certificate '+name)
        ranking_operations += ops
        same(r['checks'], check['checks'], 'checks public copy')
        child = proposal['branches']['primary']['candidate'] if check['checks']['primary']['accepted'] else parent
        same(r['child'], child, 'deployed child'); same(check['deployed'], child, 'deployed check')
        adopted = child['key'] != parent['key']; same(r['adopted'], adopted, 'actual adoption')
        alloc_id = r['check_record']+1; binding = bodies[alloc_id]
        require(records[alloc_id]['kind'] == 'R30_allocator_binding', 'allocator binding event')
        same(binding['bundle'], child, 'exact bound bundle')
        same(records[alloc_id]['deps'], [r['check_record']], 'allocator permission support')
        task_id = alloc_id+1
        require(records[task_id]['kind'] == 'R30_actual_task_binding', 'task binding event')
        same(bodies[task_id]['before'], current_task, 'previous task')
        current_task = tasks[acells[(child['key'], 0)]['task']]
        same(bodies[task_id]['after'], current_task, 'actual selected solver')
        same(bodies[task_id]['allocator'], child, 'solver uses child')
        m = {k: mean(v) for k, v in r['evaluation_only']['blocks'].items()}
        same(r['evaluation_only']['means'], m, 'evaluation means from blocks')
        delta, gp, gi = m['parent']-m['child'], m['previous']-m['child'], m['initial']-m['child']
        same([r['delta'], r['gamma_previous'], r['gamma_initial']], [delta, gp, gi], 'causal differences')
        same(r['strict_empirical_link'], g>0 and previous_adopted and adopted and min(delta,gp,gi)>1e-12,
             'strict linked actual generations')
        actual_key = proposal['branches']['primary']['candidate']['key']
        for field, name, invert in [('geometry_changes_proposal','raw',True),
                                    ('wrong_association_changes_proposal','shuffled',True),
                                    ('graph_proposal_identical','graph',False)]:
            match = proposal['branches'][name]['candidate']['key'] == actual_key
            same(r[field], not match if invert else match, 'proposal effect '+field)
        pcost = engine_cost(list(cells.values()), bm, tasks, histories,
                            24+7*(24+3*(len(histories)-3)), ops)
        same(r['proposal_cost'], pcost, 'proposal instrumented costs')
        same(r['adoption_cost'], engine_cost(list(acells.values()), bm, tasks, fresh, 57), 'adoption costs')
        # Evaluator cells already fully reconstructed by frozen arithmetic verifier.
        # Its aggregate costs are not re-derived here: counted but remain producer-instrumented.
        previous, parent, previous_adopted = parent, child, adopted
    rounds = x['rounds']; flags = [r['strict_empirical_link'] for r in rounds]
    summary = {'updates': sum(r['adopted'] for r in rounds), 'strict_empirical_links': sum(flags),
        'adjacent_links': any(a and b for a,b in zip(flags,flags[1:])),
        'regressions': sum(r['delta'] < -1e-12 for r in rounds),
        'mean_test_loss': mean(r['evaluation_only']['means']['child'] for r in rounds),
        'mean_recursive_gain': mean(r['gamma_initial'] for r in rounds[1:]),
        'mean_geometry_gain': mean(r['evaluation_only']['means']['raw']-r['evaluation_only']['means']['child'] for r in rounds),
        'mean_dimension': mean(r['space']['dimension'] for r in rounds),
        'mean_classes': mean(r['space']['classes'] for r in rounds),
        'changed_proposals': sum(r['geometry_changes_proposal'] for r in rounds),
        'graph_identical': all(r['graph_proposal_identical'] for r in rounds)}
    same(x['summary'], summary, 'trajectory summary')
    pressure = x['pressure']; root = pressure['withdrawn_root']
    refs = [r for r in records if r['kind'] == 'R31_revisit_withdrawn_history']
    require(parent['key'] == bodies[alloc_id]['bundle']['key'] and alloc_id in x['invalid'], 'final permission revoked')
    require(len(refs)==1 and refs[0]['refs']==[root] and refs[0]['seq'] not in x['invalid'], 'history survives')
    require(all(pressure[k] for k in ('entry_stopped','body_unchanged','reference_survives','recomputed_invalidity_matches')),
            'reported live pressure')
    return {'passed': True, 'generation_links': len(rounds), 'ranking_branches': 7*len(rounds),
            'verified_ranking_ast_operations': ranking_operations, 'arithmetic': reference,
            'limits': 'not full process isolation, CPU, evaluator cost instrumentation or independent physical world'}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', choices=('A', 'B'))
    parser.add_argument('--linkage-only', action='store_true',
                        help='Reuse the frozen runner arithmetic receipt after checking raw hash')
    args = parser.parse_args()
    receipts = []
    for batch in ((args.batch,) if args.batch else ('A', 'B')):
        base = ROOT/'results'/'r28_r31'/batch
        summary = json.loads((base/'SUMMARY.json').read_text())
        require(summary['seeds'] == list(range(43100 if batch=='A' else 44100,
                                               43108 if batch=='A' else 44108)), 'formal seeds')
        require(len(summary['archives']) == 24, 'formal archives')
        for row in summary['archives']:
            packed = (base/row['file']).read_bytes(); raw=lzma.decompress(packed)
            require(sha256(packed).hexdigest()==row['xz_sha256'] and
                    sha256(raw).hexdigest()==row['raw_sha256'], 'archive checksum')
            x=json.loads(raw); audit=audit_episode(x, run_arithmetic=not args.linkage_only)
            if args.linkage_only:
                require(row['verification']['passed'], 'original arithmetic receipt')
                audit['arithmetic'] = row['verification']
                audit['arithmetic_source'] = 'frozen runner before serialization; raw SHA checked here'
            method=next(r for r in summary['rows'] if r['seed']==x['seed'])['methods'][x['mode']]
            same(method, {**x['summary'], 'actual_cost': x['actual_cost'], 'pressure': x['pressure']},
                 'summary row from original archive')
            receipts.append({'batch':batch,'file':row['file'],**audit})
        print(batch, '24 archives linkage passed; arithmetic receipt origin recorded', flush=True)
    target=ROOT/'results'/'r28_r31'/('SUPPLEMENTAL_AUDIT_'+args.batch+'.json' if args.batch else 'SUPPLEMENTAL_AUDIT.json')
    target.write_text(json.dumps({'status':'VERIFIED', 'archive_count':len(receipts),
        'post_freeze_read_only':True,'learner_modified':False,'receipts':receipts},ensure_ascii=False,indent=2)+'\n')
    print(target)


if __name__=='__main__': main()
