"""Persistent agent. Reuses the historical refs/deps ledger, not its faulty M8 reader.
Fault schedule, raw world state and historical author labels are not inputs.
"""
import json
from collections import Counter
from itertools import product
from dataclasses import dataclass, field
from hashlib import sha256
from library_m8.core import Ledger
from .world import Judge, MOD

HYPOTHESES = tuple(product((1, -1), range(MOD), range(MOD), range(1, MOD)))
METHODS = ('library', 'plain', 'recent', 'masked', 'no_revision', 'recalibrate')


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def predicted(h, query):
    kind, value = query
    if kind == 'self':
        return (h[0] * value) % MOD
    if kind == 'w0':
        return (value + h[1]) % MOD
    if kind == 'w1':
        return (value + h[2]) % MOD
    return (h[3] * value) % MOD


def compatible(h, frame, omit_self=False):
    if not omit_self and frame['action'] != h[0] * frame['delta'] * frame['inverse'] % MOD:
        return False
    before, after, obj = frame['before'], frame['after'], frame['object']
    for o in range(2):
        if (before[0]['positions'][o] - before[1]['positions'][o]) % MOD != (h[1] - h[2]) % MOD:
            return False
        if (after[0]['positions'][o] - after[1]['positions'][o]) % MOD != (h[1] - h[2]) % MOD:
            return False
        if not omit_self:
            change = h[3] * frame['action'] % MOD if o == obj else 0
            if (after[0]['positions'][o] - before[0]['positions'][o]) % MOD != change:
                return False
    return ((after[0]['positions'][obj] - h[1]) % MOD == frame['goal']) == frame['success']


@dataclass
class Budget:
    reads: int = 0
    probes: int = 0
    ops: int = 0
    bytes: int = 0
    max_reads: int = 8
    max_probes: int = 8
    max_ops: int = 100000
    max_bytes: int = 65536

    def spend(self, key, amount=1):
        current = getattr(self, key) + amount
        if current > getattr(self, 'max_' + key):
            raise RuntimeError('budget_' + key)
        setattr(self, key, current)

    def export(self):
        return {k: getattr(self, k) for k in ('reads', 'probes', 'ops', 'bytes')}


class Queen:
    def __init__(self, method='library'):
        if method not in METHODS:
            raise ValueError('unknown comparator')
        self.method = method
        self._judge = Judge()
        self.gain = 1
        self.version = 0
        self.ledger = Ledger()
        self.H = HYPOTHESES
        self.epochs = []
        self.proof_keys = []
        self.experiences = []
        self.failed_experiences = []
        self.reviews = []
        self.attributions = []
        self.tick = 0
        self.assumption = self.ledger.add('assumption', 'queen', {'scope': 'initial_unknown'})
        self.certificate = None
        self.bindings = None
        self.last_review = None
        self.cost = Counter()
        self.audit_calls = 0
        self.blocked_calls = 0
        self.rollbacks = 0
        self.identity_uncertainty = {}

    def valid(self):
        return (self.certificate is not None and self.certificate not in self.ledger.invalid
                and self.bindings is not None and self.bindings[0] is self._judge
                and self.bindings[1:] == (self.gain, self.version))

    def decide(self, observed_position, goal):
        """Every world-task invocation passes this gate. Latent drift is not magically known."""
        if not self.valid():
            self.blocked_calls += 1
            raise PermissionError('no_current_certificate')
        return self._judge((goal-observed_position) % MOD, pow(self.gain, -1, MOD))

    def _read(self, key, budget):
        record = self.ledger.records[key]
        budget.spend('reads')
        budget.spend('bytes', len(record.body.encode()))
        value = json.loads(record.body)
        if self.method == 'plain':
            value = json.loads(json.dumps(value))
        return value

    def _select_history(self, current_key, budget):
        """Old slices are comparative evidence, never silently treated as current-state samples."""
        refs = []
        if current_key is not None and self.method != 'masked':
            self._read(current_key, budget)
            refs.append(current_key)
        if self.method not in ('recent', 'masked') and self.experiences:
            older = [k for k in self.experiences if k != current_key]
            if older:
                # Revisit a prior failed decision first, otherwise an early successful anchor.
                previous_failures = [k for k in self.failed_experiences if k != current_key]
                key = previous_failures[-1] if previous_failures else older[0]
                self._read(key, budget)
                refs.append(key)
        if self.last_review is not None and self.method not in ('recent', 'masked'):
            self._read(self.last_review, budget)
            refs.append(self.last_review)
        return tuple(dict.fromkeys(refs))

    def _probe(self, port, query, budget):
        budget.spend('probes')
        if query[0] == 'self':
            # Audit-only invocation has no world effect. It is counted, not an execution bypass.
            reply = {'value': self._judge(query[1], 1), 'input_delta': query[1], 'inverse': 1}
        else:
            reply = port.probe(query)
        key = self.ledger.add('probe', 'queen' if query[0] == 'self' else 'apparatus',
                              {'tick': self.tick, 'query': list(query), 'reply': reply})
        if query[0] == 'motor' and reply['value'] != reply['second_delta']:
            return key, None
        return key, reply['value']

    def _reopen(self, reason, key=None):
        old = self.assumption
        self.epochs.append({'end_tick': self.tick, 'candidates': [list(h) for h in self.H],
                            'assumption': old, 'reason': reason})
        self.ledger.revoke(old, reason)
        self.certificate = None
        self.assumption = self.ledger.add('assumption', 'queen',
            {'tick': self.tick, 'scope': 'new_current_explanation_required', 'reason': reason},
            refs=(() if key is None else (key,)))
        self.H = HYPOTHESES
        self.proof_keys = []

    def review(self, port, current_key=None, bootstrap=False):
        budget = Budget()
        self.audit_calls += 1
        refs = self._select_history(current_key, budget)
        H = self.H
        if current_key is None and self.experiences and not self.valid():
            # No new action history exists while execution is suspended; remeasure rather
            # than reassert a stale diagnosis when changes may have happened during abstention.
            H = HYPOTHESES
            self.proof_keys = []
        current = json.loads(self.ledger.records[current_key].body) if current_key is not None else None
        # A hidden-history control may not recover the same material from the private cache.
        if self.method == 'masked' and current is not None:
            H = tuple(h for h in HYPOTHESES if compatible(h, current, omit_self=True))
            budget.spend('ops', len(HYPOTHESES))
        before_candidates = len(H)
        inference_steps = []
        evidence = []
        candidate = None
        changed = []
        diagnosis = None
        query_pool = [('self', 1), ('w0', 0), ('w1', 0), ('motor', 1)]
        status = 'unresolved'
        pending_undo = None
        old_model = {'gain': self.gain, 'version': self.version}
        try:
            if self.method == 'recalibrate':
                H = HYPOTHESES
            while H and (len(H) > 1 or (self.method == 'recalibrate' and query_pool)):
                if not query_pool or budget.probes >= 4:
                    break  # Four calls reserved for adoption validation, equally for every method.
                best, best_score = None, -1
                for query in query_pool:
                    budget.spend('ops', len(H))
                    groups = Counter(predicted(h, query) for h in H)
                    score = len(H)**2 - sum(n*n for n in groups.values())
                    if score > best_score:
                        best, best_score = query, score
                query_pool.remove(best)
                key, value = self._probe(port, best, budget)
                evidence.append(key)
                budget.spend('ops', len(H))
                previous_count = len(H)
                H = tuple(h for h in H if value is not None and predicted(h, best) == value)
                inference_steps.append({'query': list(best), 'before': previous_count, 'after': len(H), 'reply': value})
            self.H = H
            if not H:
                status = 'model_inconsistent'
            elif len(H) == 1:
                h = H[0]
                diagnosis = {'self': h[0] != 1, 'worker0': h[1] != 0,
                             'worker1': h[2] != 0, 'environment': h[3] != self.gain}
                if self.method == 'no_revision' and not bootstrap:
                    status = 'revision_disabled'
                else:
                    saved_judge, saved_gain = self._judge, self.gain
                    decoder_changes = [(-h[1]) % MOD, (-h[2]) % MOD]
                    pending_undo = (saved_judge, saved_gain, decoder_changes)
                    if diagnosis['self']:
                        self._judge = Judge()
                        changed.append('self')
                    for w, amount in enumerate(decoder_changes):
                        if amount:
                            port.adjust_decoder(w, amount)
                            changed.append('worker' + str(w))
                    if diagnosis['environment']:
                        self.gain = h[3]
                        changed.append('control_model')
                    # Validation queries differ from identification probes. Their results may reject,
                    # never silently retune this candidate in place.
                    good = True
                    for query, expected in [(('self', 3), 3), (('w0', 3), 3),
                                            (('w1', 3), 3), (('motor', 2), 2*self.gain % MOD)]:
                        key, value = self._probe(port, query, budget)
                        evidence.append(key)
                        good = good and value == expected
                    if good:
                        if changed:
                            self.version += 1
                        self.H = ((1, 0, 0, self.gain),)
                        candidate = {'gain': self.gain, 'version': self.version,
                                     'controlled': ['judge_binding', 'worker_decoders', 'issued_actions'],
                                     'not_controlled': ['sensor_physics', 'actuator_gain', 'past_authors'],
                                     'refutation': 'new_action_or_observation_violates_any_saved_prediction'}
                        self.certificate = self.ledger.add('certificate', 'queen',
                            {'tick': self.tick, 'self_model': candidate,
                             'scope': 'stationary_mod7_model_until_contradicted'},
                            refs=refs, deps=tuple(dict.fromkeys((self.assumption,) + tuple(self.proof_keys) + tuple(evidence))))
                        self.bindings = (self._judge, self.gain, self.version)
                        status = 'adopted' if changed else 'confirmed'
                        pending_undo = None
                    else:
                        self._judge, self.gain = saved_judge, saved_gain
                        for w, amount in enumerate(decoder_changes):
                            if amount:
                                port.adjust_decoder(w, -amount)
                        self.rollbacks += 1
                        self.ledger.revoke(self.assumption, 'candidate_failed_validation')
                        self.certificate = None
                        status = 'rolled_back'
                        pending_undo = None
            if status not in ('adopted', 'confirmed'):
                self.certificate = None
        except RuntimeError as exc:
            # Budget failure must never be interpreted as adoption.
            status = str(exc)
            if pending_undo is not None:
                self._judge, self.gain, decoder_changes = pending_undo
                for w, amount in enumerate(decoder_changes):
                    if amount:
                        port.adjust_decoder(w, -amount)
                self.rollbacks += 1
                self.ledger.revoke(self.assumption, 'budget_failure_during_adoption')
            self.certificate = None
        result = {'tick': self.tick, 'status': status, 'old_model': old_model,
                  'diagnosis': diagnosis, 'proposed_changes': changed,
                  'applied_changes': changed if status == 'adopted' else [],
                  'candidates': [list(h) for h in H], 'candidate_count': len(H), 'initial_candidate_count': before_candidates, 'inference_steps': inference_steps,
                  'history_reads': list(refs), 'evidence': evidence,
                  'version': self.version, 'self_model': candidate, 'cost': budget.export()}
        self.last_review = self.ledger.add('review', 'queen', result,
            refs=tuple(dict.fromkeys(refs + tuple(evidence))), deps=tuple(evidence))
        self.reviews.append(result)
        self.cost.update(budget.export())
        return result

    def experience(self, port, obj, goal):
        if not self.valid():
            # Keep old hypotheses in immutable epochs; a fresh audit does not receive a correct model.
            if self.assumption in self.ledger.invalid:
                self._reopen('retry_after_rejected_explanation')
            self.review(port, bootstrap=not self.experiences)
        before = port.sense()
        observed = before[obj]['positions'][obj]
        if not self.valid():
            self.blocked_calls += 1
            return {'tick': self.tick, 'acted': False, 'success': False, 'version': self.version}
        action = self.decide(observed, goal)
        inverse = pow(self.gain, -1, MOD)
        predicted_positions = [row['positions'][:] for row in before]
        for positions in predicted_positions:
            positions[obj] = (positions[obj] + self.gain * action) % MOD
        intent = self.ledger.add('intention', 'queen',
            {'tick': self.tick, 'object': obj, 'goal': goal, 'before': before,
             'delta': (goal-observed) % MOD, 'inverse': inverse, 'action': action,
             'prediction': {'worker_positions_after': predicted_positions, 'success': True},
             'version': self.version},
             refs=(() if self.last_review is None else (self.last_review,)))
        after = port.move(obj, action, goal)
        frame = {'tick': self.tick, 'object': obj, 'goal': goal, 'before': before,
                 'queen_available': {'worker_channel': obj, 'observed': observed,
                                     'gain_belief': self.gain, 'hypotheses': [list(h) for h in self.H]},
                 'delta': (goal-observed) % MOD, 'inverse': inverse, 'action': action,
                 'prediction': {'worker_positions_after': predicted_positions, 'success': True},
                 'after': after['workers'], 'success': after['success'], 'version': self.version,
                 'read_history': [] if self.last_review is None else [self.last_review], 'intention_slice': intent}
        key = self.ledger.add('experience', 'queen', frame,
                             refs=(intent,) + (() if self.last_review is None else (self.last_review,)))
        self.experiences.append(key)
        if not frame['success']:
            self.failed_experiences.append(key)
        self.cost['ops'] += 2 + len(self.H)
        new_H = tuple(h for h in self.H if compatible(h, frame))
        if not new_H:
            self._reopen('observed_history_contradiction', key)
            self.cost['ops'] += len(self.H)
            self.H = tuple(h for h in self.H if compatible(h, frame))
            self.proof_keys = [key]
            self.review(port, key)
        else:
            self.H = new_H
        return dict(frame, acted=True, slice=key)

    def attribute(self, packet):
        """No actor ids, fingerprints, genealogy keys or truth labels enter this interface.
        This identifies compatibility with recorded intervention effects, not metaphysical identity.
        """
        if set(packet) != {'observations'}:
            raise ValueError('identity_metadata_not_allowed')
        rows = packet['observations']
        for row in rows:
            if set(row) != {'local_effect', 'paths'} or len(row['paths']) != 2:
                raise ValueError('noncanonical_anonymous_row')
        budget = Budget()
        candidates = {0, 1}
        read = []
        n = len(rows)
        if self.method == 'recent':
            order = list(reversed(range(n)))
        else:
            # Spread inspection across time; neither row values nor hidden author guide selection.
            order = []
            todo = [(0, n-1)] if n else []
            while todo:
                left, right = todo.pop(0)
                for i in (left, right):
                    if i not in order:
                        order.append(i)
                if right-left > 1:
                    middle = (left+right)//2
                    todo += [(left+1, middle), (middle+1, right-1)]
        for i in order[:budget.max_reads]:
            row = rows[i]
            budget.spend('reads')
            budget.spend('bytes', len(json.dumps(row).encode()))
            budget.spend('ops', 2)
            read.append(i)
            local = None if self.method == 'masked' else row['local_effect']
            if local is not None:
                candidates = {c for c in candidates if row['paths'][c] == local}
        probability = [1/len(candidates) if c in candidates else 0.0 for c in range(2)] if candidates else [None, None]
        result = {'candidates': sorted(candidates), 'probability': probability,
                  'status': 'unique' if len(candidates)==1 else ('ambiguous' if candidates else 'inconsistent'),
                  'read_slices': read, 'cost': budget.export()}
        obs = self.ledger.add('anonymous_history', 'apparatus', packet)
        self.ledger.add('attribution_review', 'queen', result, refs=(obs,), deps=(obs,))
        self.identity_uncertainty[digest(packet)] = result
        self.attributions.append(result)
        self.cost.update(budget.export())
        return result
