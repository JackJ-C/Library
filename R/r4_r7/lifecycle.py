"""Scoped current self models on the actual R1/M54 Queen lineage.
Old claims stay readable as history; access to a current claim is separately gated.
This adapter is researcher-written, not an autonomous meta-code repair.
"""
import json
from src.core import Queen as R3Queen, PRIOR
from library_m54.queen import NotLicensed

class Queen(R3Queen):
    def __init__(self, seed=0, method='library'):
        super().__init__(seed, method)
        self.own_status = {}
        self.own_binding = None
        self.monitor = None
        self.search_program = None
        self.search_history = []
        self.competence_history = []

    def historical_self(self, key):
        if type(key) is not int or not 0 <= key < len(self.ledger.records):
            raise ValueError('unknown history key')
        record = self.ledger.records[key]
        if record.kind != 'R_own_model':
            raise ValueError('not a self-model')
        return {'record': json.loads(record.body), 'key': key,
                'current': key == self.self_permission and key not in self.ledger.invalid
                    and self.own_binding is self._emit,
                'history_only': True}

    def current_self(self):
        key = self.self_permission
        if key is None:
            return {'status':'unknown', 'options': None}
        if key in self.ledger.invalid or self.own_binding is not self._emit:
            return {'status':'stale', 'options': None, 'history_key': key}
        return {'status':'supported', 'options': list(self.self_options), 'history_key':key,
                'scope':'linear emission; stationary until contradicted'}

    def r_valid(self):
        return super().r_valid() and self.current_self()['status']=='supported'

    def _revoke_own(self, reason):
        key = self.self_permission
        if key is not None and key not in self.ledger.invalid:
            self.ledger.revoke(key, reason)
            self.own_status[key]='stale'
        self.own_binding = None

    def withdraw(self, reason, refs=()):
        # Do not infer locus from the exception string. Compare preserved prediction
        # and own issued receipt, which predate this decision.
        forecasts=[]; receipts=[]
        for k in refs:
            r=self.ledger.records[k];data=json.loads(r.body)
            if r.kind=='R_prospective_self': forecasts.append(data)
            if 'issued' in data and 'requested' in data: receipts.append(data)
        contradicted=any(a['predicted_issued']!=b['issued']
                         and a['requested']==b['requested'] for a in forecasts for b in receipts)
        if contradicted:
            self._revoke_own('actual own receipt contradicts prospective self-model')
        return super().withdraw(reason,refs)

    def diagnose(self, port):
        previous=self.self_permission
        out=super().diagnose(port)
        if out['status']=='adopted':
            if previous is not None and previous!=self.self_permission and previous not in self.ledger.invalid:
                self.ledger.revoke(previous,'new current self-model supersedes old claim; old content retained')
            self.own_binding=self._emit
            self.own_status[self.self_permission]='supported'
        elif not self.H or len({h[0] for h in self.H})!=1:
            self._revoke_own('fresh self evidence insufficient or inconsistent')
        return out

    def withdraw_evidence(self,key,reason):
        self.ledger.revoke(key,reason)
        return {'task_valid':self.r_valid(), 'self':self.current_self(),
                'worker_supported':self.calibration not in self.ledger.invalid,
                'world_supported':self.scope not in self.ledger.invalid}
