"""Evaluation-only world changes, author labels and future tasks. No imports by Queen.
An independent seed denotes an entire trajectory, not each correlated task/row.
"""
import copy
from collections import Counter
from random import Random
from .queen import Queen, METHODS, digest
from .world import World, Port, MOD

IDENTITY_CASES = ('changed_self', 'distinct_control', 'same_behavior',
                  'anonymous_reorder', 'state_merge', 'merge_with_history')


def fault_schedule(seed):
    rng = Random(seed ^ 0x5A193)
    kinds = ['self', 'worker0', 'environment', 'combined', 'worker1', 'healthy']
    rng.shuffle(kinds)
    return [(7 + 8*i + rng.randrange(3), kind, rng.randrange(1, MOD))
            for i, kind in enumerate(kinds)]


def inject(world, queen, kind, amount):
    if kind in ('self', 'combined'):
        queen._judge.sign = -1
    if kind in ('worker0', 'combined'):
        world._bias[0] = (world._bias[0] + amount) % MOD
    if kind in ('worker1', 'combined'):
        world._bias[1] = (world._bias[1] + amount) % MOD
    if kind in ('environment', 'combined'):
        world._gain = (world._gain - 1 + amount) % (MOD-1) + 1
        # amount=6 would leave the gain unchanged: still a valid no-change event.


def future_check(world, queen, seed, old_judge=None, old_gain=None, old_decoders=None):
    """Read-only evaluator trials; no results fed to the diagnostic or history selector."""
    rng = Random(seed)
    output = []
    for _ in range(12):
        trial = copy.deepcopy(world)
        trial._positions = [rng.randrange(MOD), rng.randrange(MOD)]
        obj, goal = rng.randrange(2), rng.randrange(MOD)
        before = trial._positions[:]
        observations = trial.sense()
        previous = copy.deepcopy(trial)
        previous.decoders = old_decoders[:] if old_decoders is not None else previous.decoders
        old_position = previous.sense()[obj]['positions'][obj]
        old_action = (old_judge or queen._judge)((goal-old_position) % MOD, pow(old_gain or queen.gain,-1,MOD))
        old_success = previous.move(obj,old_action,goal)['success']
        try:
            action = queen.decide(observations[obj]['positions'][obj], goal)
            success = trial.move(obj, action, goal)['success']
            output.append({'positions': before, 'object': obj, 'goal': goal,
                           'action': action, 'success': success, 'old_action': old_action, 'old_success': old_success})
        except PermissionError:
            output.append({'positions': before, 'object': obj, 'goal': goal,
                           'action': None, 'success': False, 'old_action': old_action, 'old_success': old_success})
    return output


def anonymous_packet(queen, seed, case):
    """Views contain no ids, authors, fingerprints or refs. Real past intervention effects
    come from this same Queen's executed slices. Synthetic anonymous competing tracks
    model a trusted observation interface; they are not autonomous physical agents.
    """
    rng = Random(seed)
    frames = [__import__('json').loads(queen.ledger.records[k].body) for k in queen.experiences]
    if len(frames) >= 10:
        indices = [i*(len(frames)-1)//9 for i in range(10)]
        bad = [i for i,f in enumerate(frames) if f['action'] != f['delta']*f['inverse'] % MOD]
        if bad and case == 'changed_self':
            indices[4] = bad[0]
        selected = [frames[i] for i in indices]
    else:
        selected = frames
    actual = [((f['after'][0]['positions'][f['object']] -
                f['before'][0]['positions'][f['object']]) % MOD) for f in selected]
    if not actual:
        actual = [0]  # Explicit missing/degenerate history; no invented actor evidence.
    actual = (actual * (10//len(actual)+1))[-10:]
    other = list(actual)
    ambiguous = case in ('same_behavior', 'state_merge')
    if not ambiguous:
        # A single counterfactual path difference; placement randomized independently of author.
        witness = rng.randrange(10)
        other[witness] = (other[witness] + rng.randrange(1, MOD)) % MOD
    else:
        witness = None
    truth = rng.randrange(2)
    rows = []
    for i, effect in enumerate(actual):
        paths = [None, None]
        paths[truth], paths[1-truth] = effect, other[i]
        rows.append({'local_effect': effect, 'paths': paths})
    # Merge without surviving predecessor evidence leaves both completions possible;
    # the known-history merge retains its earlier separating record.
    packet = {'observations': rows}
    return packet, truth, {'case': case, 'ambiguous_full_view': ambiguous, 'witness_index': witness,
                          'actual_frame_count': len(frames),
                          'old_judgment_differs_from_current': any(f['action'] != f['delta']*f['inverse'] % MOD for f in selected), 'synthetic_anonymous_port': True,
                          'merge_projection': {'before':[0,3], 'after':[2,2], 'predecessor_link_retained':case=='merge_with_history'} if 'merge' in case else None}


def timeline(seed, method, ticks=72):
    rng = Random(seed ^ 0x15376)
    world, queen = World(seed), Queen(method)
    port = Port(world)
    object_id, ledger_id = id(queen), id(queen.ledger)
    changes = {t: (kind, amount) for t, kind, amount in fault_schedule(seed)}
    steps, audits, owners, counts = [], [], [], Counter()
    counts['trajectories'] = 1
    accepted_versions = []
    for tick in range(ticks):
        queen.tick = world.tick = tick
        if tick in changes:
            inject(world, queen, *changes[tick])
        before_truth, before_gain = world.truth(queen), queen.gain
        before_decoders, before_judge = world.decoders[:], queen._judge
        previous_review = len(queen.reviews)
        obj, goal = rng.randrange(2), rng.randrange(MOD)
        frame = queen.experience(port, obj, goal)
        counts['task_calls'] += 1
        counts['task_executed'] += frame['acted']
        counts['task_correct'] += frame['acted'] and frame['success']
        counts['live_failures'] += frame['acted'] and not frame['success']
        if accepted_versions and frame['acted']:
            counts['post_first_revision_tasks'] += 1
            counts['post_first_revision_correct'] += frame['success']
        steps.append({'tick': tick, 'object': obj, 'goal': goal, 'acted': frame['acted'],
                      'success': frame['success'], 'version': frame['version'],
                      'slice': frame.get('slice'), 'truth_before': list(before_truth),
                      'event': changes.get(tick)})
        for review in queen.reviews[previous_review:]:
            expected = {'self': before_truth[0] != 1, 'worker0': before_truth[1] != 0,
                        'worker1': before_truth[2] != 0, 'environment': before_truth[3] != before_gain}
            counts['audits'] += 1
            counts['resolved_audits'] += review['diagnosis'] is not None
            counts['correct_diagnoses'] += review['diagnosis'] == expected
            needed = {k for k, value in expected.items() if value}
            expected_patches = {('control_model' if k=='environment' else k) for k in needed}
            actual_patches = set(review['applied_changes'])
            counts['healthy_component_mispatch'] += len(actual_patches - expected_patches)
            counts['repair_cycles'] += review['status']=='adopted'
            holdout = []
            if review['status'] in ('adopted', 'confirmed'):
                holdout = future_check(world, queen, seed*100003 + tick*79 + 19, before_judge, before_gain, before_decoders)
                counts['future_checks'] += len(holdout)
                counts['future_correct'] += sum(r['success'] for r in holdout)
                counts['future_old_correct'] += sum(r['old_success'] for r in holdout)
                counts['future_regressions'] += sum(r['old_success'] and not r['success'] for r in holdout)
                if review['status']=='adopted':
                    accepted_versions.append(queen.version)
            audits.append({'review': review, 'expected_diagnosis': expected,
                           'truth_before': list(before_truth), 'truth_after': list(world.truth(queen)),
                           'future': holdout, 'actual_binding_replaced': queen._judge is not before_judge,
                           'decoder_before': before_decoders[:], 'decoder_after': world.decoders[:]})
        if tick in (55, 58, 61, 64, 67, 70):
            case = IDENTITY_CASES[(tick-55)//3]
            packet, truth, meta = anonymous_packet(queen, seed*97 + tick, case)
            answer = queen.attribute(packet)
            used = answer['read_slices']
            visible_candidates = [c for c in range(2) if all(
                method=='masked' or packet['observations'][i]['paths'][c] ==
                packet['observations'][i]['local_effect'] for i in used)]
            counts['attribution_cases'] += 1
            counts['attribution_set_sound'] += truth in answer['candidates']
            counts['attribution_read_consistent'] += answer['candidates']==visible_candidates
            counts['attribution_unique'] += answer['status']=='unique'
            counts['attribution_unique_correct'] += answer['candidates']==[truth]
            counts['full_view_identifiable'] += not meta['ambiguous_full_view']
            counts['identified_when_identifiable'] += not meta['ambiguous_full_view'] and answer['candidates']==[truth]
            counts['symmetric_cases'] += meta['ambiguous_full_view']
            counts['symmetric_correct_uncertainty'] += meta['ambiguous_full_view'] and answer['probability']==[0.5,0.5]
            counts['false_certain'] += answer['status']=='unique' and truth not in answer['candidates']
            owners.append({'tick': tick, 'public_packet': packet, 'answer': answer,
                           'truth_hidden_from_queen': truth, **meta})
        if id(queen) != object_id or id(queen.ledger) != ledger_id:
            raise AssertionError('continuous instance replaced')
    counts['three_cycles'] = int(counts['repair_cycles'] >= 3)
    counts['state_retained'] = int(queen.version==len(accepted_versions) and
                                  len(queen.experiences)==counts['task_executed'])
    counts['rollbacks'] = queen.rollbacks
    counts['blocked_calls'] = queen.blocked_calls
    for key, value in queen.cost.items():
        counts['cost_'+key] = value
    trace = {'instance_preserved': id(queen)==object_id and id(queen.ledger)==ledger_id, 'steps': steps, 'audits': audits, 'attribution': owners,
             'ledger': queen.ledger.export(), 'invalid': sorted(queen.ledger.invalid),
             'unresolved_epochs': queen.epochs}
    return {'seed': seed, 'method': method, 'counts': dict(counts), 'trace': trace}


def pressure_cases():
    result = {}
    # Wrong calibration induces an actual decoder edit, then validation must restore it.
    for case in ('misleading_reference', 'nonlinear_sensor'):
        q, w = Queen(), World(42)
        w.lie_at_zero = case == 'misleading_reference'
        w.nonlinear_worker = case == 'nonlinear_sensor'
        old_binding, old_decoders = q._judge, w.decoders[:]
        outcome = q.review(Port(w), bootstrap=True)
        blocked = False
        try:
            q.decide(0, 1)
        except PermissionError:
            blocked = True
        result[case] = {'status': outcome['status'], 'rollback': q.rollbacks,
                        'restored': old_binding is q._judge and old_decoders==w.decoders,
                        'permit': q.valid(), 'blocked': blocked, 'review': outcome}
    # Contradiction discovered after valid deployment revokes downstream permission,
    # while a new review can reference the obsolete certificate without inheriting its truth.
    q, w = Queen(), World(43)
    q.review(Port(w), bootstrap=True)
    old_cert = q.certificate
    q._reopen('trusted_counterexample')
    denied = False
    try:
        q.decide(0, 1)
    except PermissionError:
        denied = True
    r = q.ledger.add('review', 'queen', {'old_approval_unjustified': True}, refs=(old_cert,))
    result['revocation'] = {'old_certificate_invalid': old_cert in q.ledger.invalid,
                            'execution_denied': denied, 'review_survives': r not in q.ledger.invalid}
    # Same public data, opposite hidden author: no classifier can be certain in both worlds.
    q, w = Queen(), World(2)
    q.experience(Port(w), 0, 4)
    packet, _, _ = anonymous_packet(q, 1, 'same_behavior')
    a = q.attribute(packet)
    swapped = {'observations': [{'local_effect': r['local_effect'], 'paths': r['paths'][::-1]}
                                for r in packet['observations']]}
    b = q.attribute(swapped)
    result['symmetry'] = {'identical_public_view': digest(packet)==digest(swapped),
                           'probabilities': a['probability'], 'swapped': b['probability'],
                           'opposite_hidden_authors_possible': True}
    try:
        q.attribute(dict(packet, author_id='queen'))
        rejected = False
    except ValueError:
        rejected = True
    result['identity_label_injection_rejected'] = rejected
    # Out-of-family actuator only differs for action3: action1/2 probes miss it.
    q, w = Queen(), World(4)
    w.nonlinear_motor = True
    q.review(Port(w), bootstrap=True)
    q.tick = 1
    before = w._positions[0]
    goal = (before+3) % MOD
    f = q.experience(Port(w), 0, goal)
    result['latent_motor'] = {'initially_accepted': bool(f['acted']),
                             'future_action_failed': not f['success'],
                             'contradiction_raised': bool(q.epochs),
                             'post_review_valid': q.valid()}
    # Observational self attribution can also fail if the causal-port assumptions fail.
    fake = {'observations':[{'local_effect':1, 'paths':[1,2]} for _ in range(10)]}
    wrong = q.attribute(fake)
    result['lying_causal_port'] = {'true_author':1, 'decision':wrong,
                                   'incorrectly_certain': wrong['candidates']==[0]}
    return result


def batch(seeds):
    rows = []
    totals = {m: Counter() for m in METHODS}
    for seed in seeds:
        for method in METHODS:
            row = timeline(seed, method)
            rows.append(row)
            totals[method].update(row['counts'])
    return {'seeds': list(seeds), 'rows': rows,
            'summary': {m: dict(c) for m,c in totals.items()}}
