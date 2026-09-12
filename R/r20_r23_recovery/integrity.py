"""Content-bound current knowledge on the existing R12/R7/R3/M54 Queen.
The gate covers declared public-interface faults, not malicious same-process code.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
from r12_r15.online import Queen as PreviousQueen
from r4_r7.monitor import feature_key
from r4_r7.study import Emitter
from src.core import World, Port


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def closure(ledger, roots):
    """Include all causal supports, not historical references in general."""
    found=set();todo=list(roots)
    while todo:
        k=todo.pop()
        if type(k) is not int or not 0<=k<len(ledger.records):raise ValueError('missing evidence')
        if k in found:continue
        found.add(k);todo.extend(ledger.records[k].deps)
    return tuple(sorted(found))


def evidence_digest(ledger, keys):
    return digest([(k,ledger.records[k].kind,ledger.records[k].body,
                    ledger.records[k].refs,ledger.records[k].deps) for k in keys])


@dataclass(frozen=True)
class Seal:
    keys: tuple
    evidence_hash: str
    value_hash: str

    @classmethod
    def build(cls, ledger, roots, value):
        keys=closure(ledger, roots)
        if any(k in ledger.invalid for k in keys):raise PermissionError('withdrawn support')
        return cls(keys,evidence_digest(ledger,keys),digest(value))

    def valid(self, ledger, value):
        return (all(k not in ledger.invalid for k in self.keys)
                and self.evidence_hash==evidence_digest(ledger,self.keys)
                and self.value_hash==digest(value))


class Queen(PreviousQueen):
    def __init__(self, seed=0, method='adaptive'):
        super().__init__(seed,method)
        self.monitor_seal=None
        self.calibration_keys=[]
        self.meta_scale=1.0
        self.meta_ref=None
        self.meta_seal=None
        self.allocator=None
        self.allocator_seal=None
        self.allocator_ref=None
        self.task_binding=None
        self.task_seal=None
        self.current_history=()
        self.meta_generation=0

    def rebuild_monitor(self, keys, reason):
        ok=super().rebuild_monitor(keys,reason)
        if ok:self.monitor_seal=Seal.build(self.ledger,(self.monitor_ref,),self.monitor.export())
        return ok

    def monitor_valid(self):
        return (super().monitor_valid() and self.monitor_seal is not None
                and self.monitor_seal.valid(self.ledger,self.monitor.export()))

    def current_reliability(self, trace):
        self.notice_binding_change();cell=feature_key(trace)
        if not self.monitor_valid():return {'status':'unknown','probability':None}
        # Compute on a detached authenticated value, never a replaceable live method.
        snapshot=json.loads(canonical(self.monitor.export()))
        a,n=next(((r[2],r[3]) for r in snapshot['cells'] if tuple(r[:2])==cell),(1,2))
        return {'status':'supported','probability':a/n,'snapshot':snapshot,'model':self.monitor_ref}

    def refresh_meta(self):
        ratios=[];used=[]
        for key in self.calibration_keys[-12:]:
            if key in self.ledger.invalid:continue
            r=self.ledger.records[key];d=self.read(key)
            f=self.read(d['forecast'])
            # Forecast precedes checking; its accuracy need not be true for its occurrence to be evidence.
            if r.kind!='R22_checked_forecast' or d['forecast']>=key:raise ValueError('not a prospective pair')
            if d['forecast'] in self.ledger.invalid:continue
            observed=sum(d['validation_losses'])/len(d['validation_losses'])
            ratios.append(min(4.0,max(.25,abs(observed-f['mean'])/max(.02,f['uncert']))))
            used.append(key)
        self.meta_scale=sum(ratios)/len(ratios) if ratios else 1.0
        self.meta_ref=self.add('R20_meta_calibration',{'scale':self.meta_scale,'samples':len(used)},deps=tuple(used))
        self.meta_seal=Seal.build(self.ledger,(self.meta_ref,),self.meta_scale)
        return self.meta_scale

    def current_meta(self):
        if self.meta_seal is None or not self.meta_seal.valid(self.ledger,self.meta_scale):
            raise PermissionError('current evaluator calibration unsupported')
        return self.meta_scale

    def bind_allocator(self, ast, support=()):
        from .racing import Program
        self.current_meta()
        self.allocator=Program(ast)
        self.allocator_ref=self.add('R21_allocator_binding',{'ast':ast,'generation':self.meta_generation},
                                    deps=(self.meta_ref,*tuple(dict.fromkeys(support))))
        self.allocator_seal=Seal.build(self.ledger,(self.allocator_ref,),self.allocator.ast)

    def require_allocator(self):
        self.current_meta()
        if self.allocator_seal is None or not self.allocator_seal.valid(self.ledger,self.allocator.ast):
            raise PermissionError('current allocator unsupported')
        return self.allocator

    def bind_task(self, ast):
        from r4_r7 import search
        self.require_allocator()
        self.search_program=search.Program(ast);self.task_binding=self.search_program
        self.task_seal=Seal.build(self.ledger,(self.allocator_ref,),self.search_program.ast)

    def execute_diagnosis(self, problem, body, costs):
        from r4_r7.study import own_diagnosis
        self.require_allocator()
        if (self.search_program is not self.task_binding or self.task_seal is None
                or not self.task_seal.valid(self.ledger,self.search_program.ast)):
            raise PermissionError('unregistered task binding')
        return own_diagnosis(self,problem,body,costs)


def make_queen(seed, method='adaptive'):
    q=Queen(seed,method)
    w=World((0,0,'less',3,[(seed%6)+1,2,3,4]))
    q._emit=Emitter((seed//7)%6+1)
    q.diagnose(Port(w))
    for i in range(4):q.step(Port(w),i%2,(w.positions[i%2]+1)%7)
    q.refresh_meta()
    return q,w
