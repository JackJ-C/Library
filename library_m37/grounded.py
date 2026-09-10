"""Integrate separately committed intentions and observed outcomes into current inference.
The previous mechanical validation is preserved in library_m33, unchanged.
"""
from library_m33.queen import Queen, HYPOTHESES, compatible
from library_m33.world import MOD


class GroundedQueen(Queen):
    def _select_history(self, current_key, budget):
        if current_key is None:
            # Bootstrap, suspended retry, or no new observations: use no stale current facts.
            return super()._select_history(current_key, budget)
        outcome = self._read(current_key, budget)
        references = [current_key]
        # Only the sensory part of this latest slice is admissible here. Although the
        # human-readable export repeats intention fields, they are not used to infer self.
        budget.spend('ops', len(HYPOTHESES))
        H = tuple(h for h in HYPOTHESES if compatible(h, outcome, omit_self=True))
        self.proof_keys = [current_key]
        replay = {'tick': self.tick, 'outcome_slice': current_key,
                  'self_intention_inspected': False, 'prior_review_inspected': False}
        if self.method != 'masked':
            intention_key = outcome['intention_slice']
            intention = self._read(intention_key, budget)
            references.append(intention_key)
            self.proof_keys.append(intention_key)
            replay.update(self_intention_inspected=True, intention_slice=intention_key,
                          issued=intention['action'],
                          original_prediction=intention['prediction'])
            # A damaged backlink/receipt cannot silently qualify as a genuine intention.
            matched = (self.ledger.records[intention_key].kind == 'intention'
                       and intention_key < current_key
                       and all(intention[k] == outcome[k] for k in
                               ('tick', 'object', 'goal', 'before', 'version')))
            budget.spend('ops', len(H))
            joint = dict(outcome, delta=intention['delta'], inverse=intention['inverse'],
                         action=intention['action'])
            H = tuple(h for h in H if matched and compatible(h, joint))
        if self.last_review is not None and self.method not in ('recent', 'masked'):
            prior = self._read(self.last_review, budget)
            references.append(self.last_review)
            prior_model = prior.get('self_model')
            if prior_model is not None and replay['self_intention_inspected']:
                obj = outcome['object']
                observed = (outcome['after'][0]['positions'][obj]-outcome['before'][0]['positions'][obj]) % MOD
                anticipated = prior_model['gain']*intention['action'] % MOD
                replay.update(prior_review_inspected=True,
                              historical_control_gain=prior_model['gain'],
                              anticipated_effect=anticipated, observed_effect=observed,
                              old_control_explanation_supported=anticipated==observed,
                              limitations='sensor or off-family changes can also violate this prediction')
        self.H = H  # Cached conclusions do not bypass the retrieved intention/outcome evidence.
        replay['candidate_count_after_reinspection'] = len(H)
        key = self.ledger.add('cross_slice_reinspection', 'queen', replay,
                             refs=tuple(references), deps=tuple(self.proof_keys))
        references.append(key)
        return tuple(references)
