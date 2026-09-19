"""R34 finite sequential effect closure on the actual inherited M54 observation port.
343 observable (position0,position1,last-issued) states, 14 (object,command) actions.
Complete finite reset capability, identity emitter and stationary Markov mechanism
are declared assumptions, not discoveries or open-world guarantees.
"""
from itertools import product
from collections import deque
from types import MappingProxyType
import json
from r28_r31.space import digest

STATES = tuple(product(range(7),range(7),range(7)))
ACTIONS = tuple(product(range(2),range(7)))


def refine(transitions,outputs,states=STATES,actions=ACTIONS):
    """Greatest output-preserving deterministic bisimulation of a COMPLETE table."""
    states,actions=tuple(states),tuple(actions)
    if not states or not actions or len(set(states))!=len(states) or len(set(actions))!=len(actions):
        raise ValueError('nonempty unique state/action scopes required')
    expected={(s,a) for s in states for a in actions}
    if set(transitions)!=expected or set(outputs)!=expected:
        raise ValueError('incomplete transition evidence: UNKNOWN, not equivalent')
    universe=set(states)
    if any(t not in universe for t in transitions.values()):
        raise ValueError('transition outside declared scope')
    groups={s:0 for s in states};history=[1]
    for _ in range(len(states)+1):
        classes={};new={}
        for s in states:
            key=tuple((outputs[s,a],groups[transitions[s,a]]) for a in actions)
            new[s]=classes.setdefault(key,len(classes))
        history.append(len(classes))
        if new==groups:return groups,history
        groups=new
    raise RuntimeError('finite partition refinement exceeded its bound')


def witness(first,second,transitions,outputs,actions=ACTIONS):
    """Shortest distinguishing input word; None means equivalence in this full table."""
    queue=deque([(first,second,())]);seen={(first,second)}
    while queue:
        s,t,word=queue.popleft()
        for a in actions:
            if outputs[s,a]!=outputs[t,a]:return word+(a,)
            pair=(transitions[s,a],transitions[t,a])
            if pair not in seen:
                seen.add(pair);queue.append((*pair,word+(a,)))
    return None


def measure_cell(q,port,state,action):
    start=len(q.ledger.records)
    q.prepare(port,(state[0],state[1],0,state[2]))
    before=q.decode(port.sense())
    if before[0]!=before[1] or before[0]!=list(state[:2]) or q.last!=state[2]:
        raise RuntimeError('public reset/primer protocol failed')
    obj,command=action
    e=q.trial(port,obj,command,'R34_closure_probe')
    after=q.decode(q.read(e['observation'])['after'])
    if after[0]!=after[1] or e['issued']!=command:
        raise RuntimeError('outside calibrated identity-emitter closure scope')
    target=tuple(after[0])+(e['issued'],)
    effect=tuple((after[0][j]-state[j])%7 for j in range(2))
    return {'state':list(state),'action':list(action),'next':list(target),'output':list(effect),
            'support':list(range(start,len(q.ledger.records))),
            'intention':e['intention'],'observation':e['observation']}


def learn_closure(q,port,rows=None,repair_keys=()):
    """All unmeasured/withdrawn cells are queried; missing behavior is never invented."""
    bank={} if rows is None else {(tuple(r['state']),tuple(r['action'])):r for r in rows}
    replacements=set(repair_keys);actual=0
    for state in STATES:
        for action in ACTIONS:
            key=(state,action);existing=bank.get(key)
            invalid=existing is not None and any(x in q.ledger.invalid for x in existing['support'])
            if existing is None or key in replacements or invalid:
                bank[key]=measure_cell(q,port,state,action);actual+=1
    ordered=[bank[s,a] for s in STATES for a in ACTIONS]
    return EffectController(q,port,ordered),actual


class EffectController:
    def __init__(self,q,port,rows):
        if len(rows)!=len(STATES)*len(ACTIONS):raise ValueError('full finite scope not observed')
        self.q=q;self.port=port
        self.rows=json.loads(json.dumps(rows))
        transitions={(tuple(r['state']),tuple(r['action'])):tuple(r['next']) for r in rows}
        outputs={(tuple(r['state']),tuple(r['action'])):tuple(r['output']) for r in rows}
        groups,self.refinements=refine(transitions,outputs)
        quotient={}
        for s in STATES:
            for a in ACTIONS:
                edge=(outputs[s,a],groups[transitions[s,a]])
                if (groups[s],a) in quotient and quotient[groups[s],a]!=edge:
                    raise RuntimeError('not a congruent quotient')
                quotient[groups[s],a]=edge
        self.transitions=MappingProxyType(transitions);self.outputs=MappingProxyType(outputs)
        self.groups=MappingProxyType(groups);self.quotient=MappingProxyType(quotient)
        self._structure=(self.transitions,self.outputs,self.groups,self.quotient)
        self.memory_conflicts=[]
        for p0,p1 in product(range(7),repeat=2):
            for a in ACTIONS:
                values={outputs[(p0,p1,h),a] for h in range(7)}
                if len(values)>1:self.memory_conflicts.append({'positions':[p0,p1],'action':list(a),'effects':sorted(values)})
        self.long_witness=None
        one_step={s:tuple(outputs[s,a] for a in ACTIONS) for s in STATES}
        for i,s in enumerate(STATES):
            for t in STATES[i+1:]:
                if one_step[s]==one_step[t] and groups[s]!=groups[t]:
                    self.long_witness={'first':s,'second':t,'word':witness(s,t,transitions,outputs)};break
            if self.long_witness:break
        supports=tuple(dict.fromkeys([q.calibration,q.self_permission]+[x for r in rows for x in r['support']]))
        if any(x is None or x in q.ledger.invalid for x in supports):raise PermissionError('invalid transition support')
        self.payload={'scope':'both objects/Z7; own last issued action; calibrated identity emitter; deterministic stationary Markov/reset protocol',
                      'states':len(STATES),'actions':len(ACTIONS),'rows':self.rows,
                      'groups':[[list(s),groups[s]] for s in STATES],
                      'quotient':[[c,list(a),list(o),t] for (c,a),(o,t) in sorted(quotient.items())],
                      'refinements':self.refinements,'memory_field_needed':bool(self.memory_conflicts),
                      'memory_conflicts':self.memory_conflicts,'long_witness':self.long_witness}
        self.model_hash=digest(self.payload)
        self.license=q.add('R34_closed_effect_model',dict(self.payload,model_hash=self.model_hash),deps=supports)
        self.offsets=tuple(q.offsets);self.emitter=q._emit;self.emitter_code=q._emit.__code__
        self.expected_last=q.last
        self._bound_act=self.act;self._bound_predict=self.predict
        q.causal_act=self._bound_act;q.causal_predict=self._bound_predict
        self.binding=q.add('R34_actual_controller_binding',{'model':self.license,'model_hash':self.model_hash,
                            'entry':'Queen.causal_act','port_is_bound':True},deps=(self.license,))

    def require(self):
        q=self.q
        if self.binding in q.ledger.invalid or self.license in q.ledger.invalid:
            raise PermissionError('withdrawn causal controller')
        if (q._emit is not self.emitter or q._emit.__code__ is not self.emitter_code or tuple(q.offsets)!=self.offsets or
                q.causal_act is not self._bound_act or q.causal_predict is not self._bound_predict):
            raise PermissionError('changed controller/emitter/calibration binding')
        if any(a is not b for a,b in zip(self._structure,(self.transitions,self.outputs,self.groups,self.quotient))):
            raise PermissionError('changed transition/quotient binding')
        if q.last!=self.expected_last:raise PermissionError('unregistered persistent action-history mutation')

    def predict(self,state,action):
        self.require();state,action=tuple(state),tuple(action)
        if state not in self.groups or action not in ACTIONS:raise ValueError('outside closed state/action scope')
        return self.quotient[self.groups[state],action][0]

    def act(self,port,obj,goal):
        self.require()
        if port is not self.port:raise PermissionError('different unvalidated world capability')
        if type(obj) is not int or obj not in (0,1) or type(goal) is not int or not 0<=goal<7:
            raise ValueError('invalid object or goal')
        decoded=self.q.decode(port.sense())
        if decoded[0]!=decoded[1]:raise PermissionError('calibrated observations disagree')
        positions=decoded[0];state=tuple(positions)+(self.q.last,)
        candidates=[a for a in range(7) if (positions[obj]+self.predict(state,(obj,a))[obj])%7==goal]
        if not candidates:return {'executed':False,'reason':'no supported one-step action'}
        a=min(candidates);effect=self.predict(state,(obj,a))
        expected=[(positions[j]+effect[j])%7 for j in range(2)]
        e=self.q.trial(port,obj,a,'R34_causal_task');self.expected_last=self.q.last
        after=self.q.decode(self.q.read(e['observation'])['after'])
        ok=after[0]==after[1] and after[0]==expected and e['issued']==a
        if not ok:self.q.ledger.revoke(self.license,'new actual transition contradicts closed finite model')
        return {'executed':True,'correct':ok,'object':obj,'goal':goal,'action':a,'state':list(state),
                'predicted':expected,'observed':after,'intention':e['intention'],'observation':e['observation'],
                'model':self.license}

    def export(self):return dict(self.payload,license=self.license,binding=self.binding,model_hash=self.model_hash)
