"""Online scoped reliability from the Queen's own raw intention/observation pairs.
No evaluator success, event time, planner mode, or hidden author enters learning.
Researcher-written adapter; it is not itself an autonomously invented architecture.
"""
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from random import Random
from math import sqrt
from r4_r7.lifecycle import Queen as BaseQueen
from r4_r7.monitor import ReliabilityModel, feature_key, fast_plan
from src.core import World, Port


class MutablePlanner:
    """One callable object; the evaluator can silently change its computation regime."""
    def __init__(self):
        self.donor = False
    def __call__(self, queen, positions, obj, goal, repeats, rng):
        return fast_plan(queen, positions, obj, goal, repeats, rng, donor=self.donor)


class Queen(BaseQueen):
    def __init__(self, seed=0, method='adaptive'):
        super().__init__(seed, 'plain' if method == 'plain' else 'library')
        self.mode = method
        self.approximate_plan = MutablePlanner()
        self.planner_binding = self.approximate_plan
        self.binding_epoch = 0
        self.monitor = None
        self.monitor_ref = None
        self.monitor_scope = self.add('R12_process_scope', {'conditional': 'stationary until evidence of change'})
        self.monitor_bound = None
        self.training_keys = []
        self.recent_keys = []
        self.audit_errors = []
        self.detection_window = deque(maxlen=64)
        self.detector_reference = None
        self.epoch_start = 0
        self.last_alarm_n = -1000
        self.next_reference_n = 0
        self.alarms = []
        self.mon_updates = 0
        self.n_raw = 0
        self.clock = 0
        self.birth_q, self.birth_ledger = id(self), id(self.ledger)
        self.online_cost = defaultdict(int)

    def notice_binding_change(self):
        if self.approximate_plan is not self.planner_binding:
            self.retract_scope('registered planning callable changed')
            self.binding_epoch += 1
            self.planner_binding = self.approximate_plan
            self.epoch_start = len(self.recent_keys)
            self.detector_reference = None
            self.detection_window.clear()

    def monitor_history(self, key):
        r = self.ledger.records[key]
        if r.kind != 'R12_monitor_model':
            raise ValueError('not a recorded monitor')
        return {'body': json.loads(r.body), 'current': key == self.monitor_ref and self.monitor_valid()}

    def monitor_valid(self):
        return (self.monitor_ref is not None and self.monitor_ref not in self.ledger.invalid
                and self.monitor_scope not in self.ledger.invalid
                and self.monitor is self.monitor_bound
                and self.approximate_plan is self.planner_binding)

    def current_reliability(self, trace):
        self.notice_binding_change()
        feature_key(trace)  # strict feature schema, not a hidden identity/signature label
        if not self.monitor_valid():
            return {'status': 'unknown', 'probability': None, 'history_key': self.monitor_ref}
        if self.mode == 'global':
            p = self.monitor.total[0] / self.monitor.total[1]
        elif self.mode == 'fixed':
            p = .35 if trace['repeats'] == 1 else .75
        elif self.mode == 'compiled':
            # Independent numerical representation, no self name or historical author.
            p = direct_probability(self.monitor.export(), trace)
        else:
            p = self.monitor.probability(trace)
        return {'status': 'supported', 'probability': p, 'model': self.monitor_ref}

    def retract_scope(self, reason, evidence=()):
        if self.monitor_scope not in self.ledger.invalid:
            self.ledger.revoke(self.monitor_scope, reason)
        self.audit_errors.append(self.add('R12_scope_review', {'time': self.clock, 'reason': reason}, refs=tuple(evidence)))

    def _raw_pair(self, key):
        check = self.ledger.records[key]
        if key in self.ledger.invalid:
            raise PermissionError('withdrawn interpretation')
        if check.kind != 'R12_interpretation' or len(check.refs) != 2:
            raise ValueError('not a first-order outcome interpretation')
        i, o = check.refs
        if i in self.ledger.invalid or o in self.ledger.invalid:
            raise PermissionError('withdrawn raw support')
        intent = self.read(i); obs = self.read(o)
        if intent.get('binding_epoch') != self.binding_epoch:
            raise ValueError('different registered planner epoch')
        if intent['checked']:
            raise ValueError('checked success does not label the unexecuted quick answer')
        before = self.decode(intent['before'], intent['offsets'])
        after = self.decode(obs['after'], intent['offsets'])
        self.online_cost['raw_pair_reads'] += 2
        if before[0] != before[1] or after[0] != after[1]:
            raise ValueError('sensor disagreement')
        # Evaluate the actually executed quick answer using observations and the old goal.
        return intent['trace'], after[0][intent['object']] == intent['goal']

    def rebuild_monitor(self, keys, reason):
        self.notice_binding_change()
        keys = tuple(dict.fromkeys(k for k in keys if k not in self.ledger.invalid))
        if len(keys) < 16:
            return False
        if self.monitor_scope in self.ledger.invalid:
            self.monitor_scope = self.add('R12_process_scope', {'conditional': 'new local observation window',
                                           'time': self.clock, 'why': reason})
        model = ReliabilityModel()
        used=[]
        for k in keys:
            try: trace, correct = self._raw_pair(k)
            except (PermissionError, ValueError): continue
            model.observe(trace, correct, k); used.append(k)
        if len(used) < 16: return False
        ref = self.add('R12_monitor_model', {'time': self.clock, 'mapping': model.export(),
                       'reason': reason, 'sample_count': len(used)},
                       deps=(self.monitor_scope, *used))
        self.monitor = self.monitor_bound = model
        self.monitor_ref = ref
        self.planner_binding = self.approximate_plan
        self.mon_updates += 1
        if self.detector_reference is None and self.n_raw >= self.next_reference_n:
            self.detector_reference = model
            self.detection_window.clear()
        return True

    def update_online(self, key, forecasting_reference):
        if key is None: return
        trace, correct = self._raw_pair(key)
        self.n_raw += 1; self.recent_keys.append(key)
        if self.mode in ('frozen', 'global', 'fixed'):
            return
        if self.detector_reference is not None:
            reference_p = self.detector_reference.probability(trace)
            self.detection_window.append((trace['repeats'], int(correct)-reference_p, key, reference_p))
        alarm = False; diagnostics=[]
        if len(self.detection_window) == 64 and self.n_raw-self.last_alarm_n >= 64:
            for repeats in (1,3):
                rows=[x for x in self.detection_window if x[0]==repeats]
                mean=sum(x[1] for x in rows)/len(rows) if rows else 0
                threshold=max(.18,3*sqrt(sum(x[3]*(1-x[3]) for x in rows))/len(rows)) if rows else 1.0
                diagnostics.append([repeats,len(rows),mean,threshold])
                if len(rows)>=20 and abs(mean)>threshold: alarm=True
        if alarm:
            evidence=tuple(x[2] for x in self.detection_window)
            self.retract_scope('own raw outcome frequencies contradict current reliability reference', evidence)
            self.alarms.append({'time':self.clock,'statistics':diagnostics,'raw_count':self.n_raw})
            self.last_alarm_n=self.n_raw
            self.epoch_start=max(0,len(self.recent_keys)-48)
            self.detector_reference=None
            self.next_reference_n=self.n_raw+64
            self.detection_window.clear()
            # Suspension is real until the next predeclared update point; no future data access.
        if self.n_raw % 16 == 0 and not alarm:
            window=self.recent_keys[max(self.epoch_start,len(self.recent_keys)-96):]
            self.rebuild_monitor(window,'past-only rolling evidence')

    def execute_plan(self, world, positions, obj, goal, raw, request, trace, p, checked, mode):
        self.notice_binding_change()
        if not self.r_valid():
            raise PermissionError('underlying emitter/world calibration is not licensed')
        world.place(positions); before=Port(world).sense()
        i=self.add('R12_plan_intention', {'time':self.clock,'before':before,'object':obj,'goal':goal,
            'binding_epoch':self.binding_epoch,'raw_action':raw,'request':request,'trace':trace,'probability':p,'checked':checked,
            'offsets':self.offsets[:],'own_multiplier':self.self_options[0],
            'world_gain':self.tree[1],'mode':mode},
            refs=(() if self.monitor_ref is None else (self.monitor_ref,)))
        issued=self._emit(request)
        after=Port(world).move(obj,issued,'R12_'+mode)
        o=self.add('R12_plan_observation', {'time':self.clock,'after':after,'issued':issued}, refs=(i,))
        b=self.decode(before); a=self.decode(after)
        other=1-obj
        base_consistent=(b[0]==b[1] and a[0]==a[1] and issued==request*self.self_options[0]%7
                         and a[0][obj]==(b[0][obj]+self.tree[1]*issued)%7 and a[0][other]==b[0][other])
        if not base_consistent:
            self.retract_scope('underlying observation/emission/action premises questioned',(i,o))
            return {'intention':i,'observation':o,'label_key':None,'consistent':False,
                    'observed_goal_met':a[0][obj]==goal,'issued':issued,'after':after}
        label=None
        if not checked:
            label=self.add('R12_interpretation', {'checked':False,'time':self.clock},
                           refs=(i,o), deps=(i,o,self.calibration,self.self_permission,self.scope))
        self.online_cost['raw_actions' if not checked else 'checked_actions']+=1
        return {'intention':i,'observation':o,'label_key':label,'consistent':True,
                'observed_goal_met':a[0][obj]==goal,'issued':issued,'after':after}


def direct_probability(export, trace):
    """An ordinary indexed controller: same numeric function, no claimed experience state."""
    repeats,bin_=feature_key(trace)
    for r,b,a,n in export['cells']:
        if r==repeats and b==bin_: return a/n
    return .5


def make_queen(seed, method='adaptive'):
    from r4_r7.study import Emitter
    q=Queen(seed,method)
    w=World((0,0,'less',3,[(seed%6)+1,2,3,4]))
    q._emit=Emitter((seed//7)%6+1)
    q.diagnose(Port(w))
    q.step(Port(w),0,(w.positions[0]+1)%7)
    return q,w


def choose_check(p,remaining,slots_left):
    """Online quota: no future traces; exactly 8 of each 32 requests may be rechecked."""
    return remaining>0 and (remaining>=slots_left or (p if p is not None else .5)<.62)
