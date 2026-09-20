"""R41: researcher-controlled 2x2 deployment experiment, offline and bounded.
Reuses unchanged R37 execution code; does not restore the missing R39 implementation.
"""
import copy
import hashlib
import json
from dataclasses import asdict
from statistics import mean
from r28_r31 import study as old
from r28_r31.space import canonical, digest
from r32_r37.space import MeasuredSpace

ROOT_ROUNDS = 6
FUTURE_ROUNDS = 3
AUDIT_SLATES = 16
SEEDS = {'A': list(range(95100, 95164)), 'B': list(range(96100, 96164))}
ARMS = ('keep_update', 'keep_frozen', 'remove_update', 'remove_frozen')


def innovation(seed, phase, index, role):
    """Named external random inputs: arm names never enter this mapping."""
    return int.from_bytes(hashlib.sha256(canonical([seed, phase, index, role]).encode()).digest()[:8], 'big')


def normal(x):
    return json.loads(canonical(x))


def diff(a, b):
    return {k: a.get(k, 0)-b.get(k, 0) for k in sorted(set(a)|set(b))}


class Registry:
    def __init__(self):
        self.banks = {}

    def register(self, key, cases):
        item = [{'problem': old.serialize_problem(p), 'identified': h} for p, h in cases]
        item = normal(item)
        if key in self.banks and self.banks[key] != item:
            raise RuntimeError('named external input changed')
        self.banks[key] = item

    def acquire(self, q, key):
        cases, ref = q.acquire(old.opaque_problems(int(key)))
        self.register(key, cases)
        if not hasattr(q, '_r41_bank_keys'):
            q._r41_bank_keys = {}
        q._r41_bank_keys[ref] = key
        return cases, ref

    def evaluator(self, key):
        cases = old.problems(int(key))
        self.register(key, cases)
        return cases


def acquire_key(q, reg, seed, phase, index, role):
    key = str(innovation(seed, phase, index, role))
    cases, ref = reg.acquire(q, key)
    return cases, ref, key


def prepare_round(q, reg, seed, phase, index):
    parent = q.require_allocator()
    before_actual = asdict(q.own_diagnostic_cost)
    block, ref, fresh_key = acquire_key(q, reg, seed, phase, index, 'history')
    q.remember(block, ref)
    task_seed = innovation(seed, phase, index, 'task_pool')
    pool_seed = innovation(seed, phase, index, 'candidate_pool')
    tasks = old.task_pool(q.search_program.ast, task_seed)
    pool = old.candidate_pool(parent, pool_seed)
    engine = old.InterventionEngine(tasks, q.history)
    columns = [[engine.run(b, j) for b in pool] for j in range(3)]
    context = {'tasks': tasks, 'budget': 12, 'train': 4, 'check': 2, 'scope': 'R41 finite diagnostic bank'}
    space = MeasuredSpace(q, pool, columns, q.block_refs[:3], context)
    candidate, selection = old.choose_proposal(parent, parent, pool, space, engine, 'space')
    proposal_ref = q.add('R41_frozen_proposal', {
        'parent': parent.json(), 'tasks': tasks, 'pool': [b.json() for b in pool],
        'candidate': candidate.json(), 'selection': selection, 'space': space.public(),
        'history_records': list(q.block_refs)}, deps=(space.version,)+tuple(q.block_refs))
    new, refs, keys = [], [], []
    for j in range(4):
        b, r, k = acquire_key(q, reg, seed, phase, index, 'adoption_'+str(j))
        new.append(b); refs.append(r); keys.append(k)
    ae = old.InterventionEngine(tasks, new)
    child, check = old.adoption(parent, candidate, ae)
    check_ref = q.add('R41_empirical_adoption', {
        'proposal': proposal_ref, 'check': check, 'would_deploy': child.json(),
        'scope': 'empirical finite bank; not a future improvement-capability certificate'},
        deps=(proposal_ref,)+tuple(refs))
    row = {'phase': phase, 'index': index, 'parent': parent.json(),
        'old_task': q.search_program.ast, 'task_seed': task_seed, 'pool_seed': pool_seed,
        'tasks': tasks, 'pool': [b.json() for b in pool], 'candidate': candidate.json(),
        'would_deploy': child.json(), 'check': check, 'selection': selection,
        'history_keys': [q._r41_bank_keys[r] for r in q.block_refs],
        'history_refs': list(q.block_refs), 'adoption_keys': keys, 'adoption_refs': refs,
        'proposal_ref': proposal_ref, 'check_ref': check_ref,
        'space': space.public(), 'new_history_key': fresh_key,
        'proposal_responses': engine.export(), 'adoption_responses': ae.export(),
        'proposal_cost': dict(engine.cost), 'adoption_cost': dict(ae.cost),
        'acquisition_cost': diff(asdict(q.own_diagnostic_cost), before_actual)}
    return {'row': row, 'parent': parent, 'child': child, 'new': new, 'refs': refs,
            'tasks': tasks, 'ae': ae, 'check_ref': check_ref}


def deploy(q, world, pending, bundle, label, generation):
    parent = pending['parent']
    intervention = q.add('R41_deployment_intervention', {
        'label': label, 'installed': bundle.json(), 'proposed': pending['child'].json(),
        'researcher_controlled': label != 'natural'}, deps=(pending['check_ref'],))
    # For a deep-copied snapshot, all old integer identity bindings are replaced
    # by this explicit newly recorded binding; no old identity is claimed.
    q.previous_allocator = parent
    q.bind_allocator(bundle, (intervention,))
    chosen = pending['ae'].run(bundle, 0).task
    q.search_program = old.search.Program(pending['tasks'][chosen])
    task_ref = q.add('R41_task_binding', {'task_index': chosen, 'task_ast': q.search_program.ast,
                        'allocator': bundle.json()}, deps=(q.bundle_permission,))
    step = q.step(old.Port(world), generation % 2, (generation+4) % 7)
    if not step['executed'] or step['mismatch']:
        raise RuntimeError('inherited control continuity failed')
    for b, r in zip(pending['new'], pending['refs']):
        q.remember(b, r)
    return {'bundle': bundle.json(), 'actual_changed': bundle.key != parent.key,
            'mechanism_ast_changed': bundle.ast != parent.ast,
            'scale_changed': bundle.scale != parent.scale,
            'task_index': chosen, 'task_ast': q.search_program.ast,
            'binding': q.bundle_permission, 'intervention_ref': intervention,
            'task_ref': task_ref, 'step': step}


def run_branch(snapshot, world_snapshot, pending, reg, seed, keep, enable, label):
    q, w = copy.deepcopy(snapshot), copy.deepcopy(world_snapshot)
    prefix = q.ledger.export()
    prefix_hash = digest(prefix)
    start_bundle = pending['child'] if keep else pending['parent']
    start_pending = copy.deepcopy(pending)
    root_install = deploy(q, w, start_pending, start_bundle, label, 0)
    identity = (id(q), id(q.ledger))
    rounds = []
    for j in range(FUTURE_ROUNDS):
        p = prepare_round(q, reg, seed, 'future', j)
        installed = p['child'] if enable else p['parent']
        row = p['row']
        row['deployment'] = deploy(q, w, p, installed, 'natural' if enable else 'freeze_update', j+1)
        rounds.append(row)
        if identity != (id(q), id(q.ledger)):
            raise RuntimeError('branch Queen or ledger replaced')
    q.require_allocator()
    end = q.allocator_bundle
    end_cost = asdict(q.own_diagnostic_cost)
    root_evidence = pending['refs'][0]
    q.ledger.revoke(root_evidence, 'R41 ancestor support withdrawal diagnostic only')
    ancestor_stopped = q.bundle_permission in q.ledger.invalid
    current_evidence = rounds[-1]['adoption_refs'][-1]
    body = q.ledger.records[current_evidence].body
    q.ledger.revoke(current_evidence, 'R41 current adoption support withdrawal')
    stopped = False
    try:
        q.require_allocator()
    except PermissionError:
        stopped = True
    # An historical reference alone must not be treated as proof support.
    history = q.add('R41_after_revoke_history', {'event_kept': True}, refs=(current_evidence,))
    result = {'keep': keep, 'enable': enable, 'prefix_hash': prefix_hash,
        'root_install': root_install, 'rounds': rounds, 'endpoint': end.json(),
        'actual_updates': sum(r['deployment']['actual_changed'] for r in rounds),
        'ast_updates': sum(r['deployment']['mechanism_ast_changed'] for r in rounds),
        'actual_cost': diff(end_cost, asdict(snapshot.own_diagnostic_cost)),
        'same_instance_within_branch': identity == (id(q), id(q.ledger)),
        'ancestor_withdrawal_stopped': ancestor_stopped,
        'pressure': {'stopped': stopped, 'body_preserved': body == q.ledger.records[current_evidence].body,
                     'reference_survives': history not in q.ledger.invalid,
                     'invalid_recompute_equal': q.ledger.invalid == q.ledger.recompute()},
        'ledger_suffix': q.ledger.export()[len(prefix):], 'invalid': sorted(q.ledger.invalid)}
    if not all(result['pressure'].values()):
        raise RuntimeError('evidence withdrawal gate failed')
    return result


def semantic_branch(branch):
    # Purely external label changes are excluded; all realized computation,
    # proposed/installed mechanisms, evidence, and costs remain in this comparison.
    rows = [{k: v for k, v in r.items() if k not in ('proposal_ref','check_ref','space')}
            for r in branch['rounds']]
    return normal({'rounds': rows, 'endpoint': branch['endpoint'],
                   'updates': branch['actual_updates'], 'cost': branch['actual_cost']})


def common_audit(reg, seed, endpoints):
    """External, fixed outcome instrument. Never sent back to any Queen."""
    bundles = {b['key']: old.Bundle(b['ast'], b['scale']) for b in endpoints.values()}
    rows, values, costs = [], {k: [] for k in bundles}, {}
    for j in range(AUDIT_SLATES):
        ts = innovation(seed, 'external_audit', j, 'task_pool')
        tasks = old.task_pool(0, ts)
        key = str(innovation(seed, 'external_audit', j, 'problem'))
        cases = reg.evaluator(key)
        # Separate engines: identical endpoints are reused only as identical
        # deterministic objects, never counted as new independent measurements.
        responses = {}
        for k, bundle in bundles.items():
            eng = old.InterventionEngine(tasks, [cases])
            r = eng.run(bundle, 0)
            values[k].append(r.loss); responses[k] = r.json()
            costs.setdefault(k, []).append(dict(eng.cost))
        rows.append({'task_seed': ts, 'tasks': tasks, 'bank_key': key, 'responses': responses})
    losses = {label: mean(values[b['key']]) for label, b in endpoints.items()}
    return {'rows': rows, 'losses': losses, 'values_by_mechanism': values, 'costs': costs}


def metrics(losses):
    g_keep = losses['keep_frozen'] - losses['keep_update']
    g_remove = losses['remove_frozen'] - losses['remove_update']
    return {'benefit_keep': g_keep, 'benefit_remove': g_remove,
        'interaction': g_keep-g_remove,
        'enabled_total_effect': losses['remove_update']-losses['keep_update'],
        'frozen_root_effect': losses['remove_frozen']-losses['keep_frozen']}


def episode(seed):
    reg = Registry(); q, world = old.make_queen(seed)
    for j in range(3):
        b, ref, _ = acquire_key(q, reg, seed, 'warmup', j, 'history')
        q.remember(b, ref)
    root_rounds = []; pending = None
    for j in range(ROOT_ROUNDS):
        p = prepare_round(q, reg, seed, 'root', j)
        if p['row']['check']['accepted']:
            root_rounds.append(p['row']); pending = p; break
        p['row']['deployment'] = deploy(q, world, p, p['child'], 'natural', j)
        root_rounds.append(p['row'])
    if pending is None:
        return {'stage': 'R41', 'seed': seed, 'root_present': False,
                'root_rounds': root_rounds, 'prefix': q.ledger.export(),
                'banks': reg.banks, 'metrics': {k: 0.0 for k in metrics(dict.fromkeys(ARMS, 0.0))}}
    prefix = q.ledger.export()
    branches = {}
    for label in ARMS:
        keep = label.startswith('keep')
        enable = label.endswith('update')
        branches[label] = run_branch(q, world, pending, reg, seed, keep, enable, label)
    # Actual replay of B,C after restoration or label-only deletion; not a log edit.
    restored = run_branch(q, world, pending, reg, seed, True, True, 'restore_after_remove')
    sham = run_branch(q, world, pending, reg, seed, True, True, 'annotation_says_removed')
    controls = {'restored_equals_keep': semantic_branch(restored) == semantic_branch(branches['keep_update']),
                'annotation_equals_keep': semantic_branch(sham) == semantic_branch(branches['keep_update'])}
    if not all(controls.values()):
        raise RuntimeError('restoration/annotation control failed')
    endpoints = {k: b['endpoint'] for k, b in branches.items()}
    audit = common_audit(reg, seed, endpoints)
    effects = metrics(audit['losses'])
    local = (effects['benefit_keep'] > old.EPS and effects['interaction'] > old.EPS
             and effects['enabled_total_effect'] > old.EPS
             and branches['keep_update']['actual_updates'] > 0
             and endpoints['keep_update']['key'] != pending['child'].key)
    return {'stage': 'R41', 'seed': seed, 'root_present': True,
            'root_rounds': root_rounds, 'prefix': prefix, 'prefix_hash': digest(prefix),
            'root_parent': pending['parent'].json(), 'root_child': pending['child'].json(),
            'branches': branches, 'restored': restored, 'annotation_only': sham,
            'controls': controls, 'audit': audit, 'metrics': effects,
            'local_productive_causal_candidate': local,
            'banks': reg.banks,
            'not_claimed': 'not general RSI; finite 2x2 interaction, not natural mediation; new R41 not recovered R39'}
