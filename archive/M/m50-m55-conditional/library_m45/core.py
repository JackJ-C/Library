"""Joint source/mechanism reasoning from anonymous effects, not supplied witness IDs.
A finite deterministic permutation prior and trusted efference custody remain explicit.
"""
from collections import Counter
from dataclasses import dataclass
from itertools import permutations
import json
from library_m41.integration import Queen as LegacyQueen
from library_m37.core import NotLicensed, packet_from_views
from library_m12.core import Queen as JudgeQueen

DOMAIN = 5
MODELS = tuple((0,) + p for p in permutations(range(1, DOMAIN)))
LINEAR = tuple(tuple((g*a) % DOMAIN for a in range(DOMAIN)) for g in range(1, DOMAIN))
METHODS = ('library', 'plain', 'marginal', 'recent', 'masked', 'pooled', 'fixed_probe', 'no_revision')


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


@dataclass
class Budget:
    reads: int = 0
    ops: int = 0
    probes: int = 0
    bytes: int = 0
    max_reads: int = 1200
    max_ops: int = 1000000
    max_probes: int = 8
    max_bytes: int = 1000000

    def charge(self, field, value=1):
        n = getattr(self, field) + value
        if n > getattr(self, 'max_' + field):
            raise RuntimeError('budget:' + field)
        setattr(self, field, n)

    def export(self):
        return {f: getattr(self, f) for f in ('reads','ops','probes','bytes')}


def sensory_projection(packet):
    if set(packet) != {'paths'} or len(packet['paths']) != 3:
        raise ValueError('only three anonymous observation paths are allowed')
    result = []
    for path in packet['paths']:
        if not isinstance(path, list):
            raise ValueError('path must be list')
        clean = []
        for frame in path:
            if set(frame) != {'before','after'}:
                raise ValueError('commands/authors/ids/links are not public observations')
            for side in ('before','after'):
                value = frame[side]
                if len(value) != 2 or any(len(w) != 2 for w in value):
                    raise ValueError('two Workers, two objects')
                if any(type(v) is not int or not 0 <= v < DOMAIN for w in value for v in w):
                    raise ValueError('invalid observation')
            clean.append(json.loads(canonical(frame)))
        result.append(clean)
    if len({len(p) for p in result}) != 1:
        raise ValueError('unbalanced observed interval')
    return {'paths': result}


def fit_pairs(commands, packet, models=MODELS, budget=None):
    packet = sensory_projection(packet)
    pairs = []
    for path_index, path in enumerate(packet['paths']):
        if len(path) != len(commands):
            raise ValueError('synchronised interval mismatch')
        for model in models:
            ok = True
            for (obj, action), frame in zip(commands, path):
                if budget: budget.charge('ops')
                for worker in (0,1):
                    before, after = frame['before'][worker], frame['after'][worker]
                    if ((after[obj]-before[obj]) % DOMAIN != model[action]
                        or after[1-obj] != before[1-obj]):
                        ok = False
                        break
                if not ok: break
            if ok: pairs.append((path_index, model))
    return pairs


def common_inverse(models):
    models = tuple(set(models))
    if not models: return (None,) * DOMAIN
    output=[]
    for delta in range(DOMAIN):
        actions = {m.index(delta) for m in models}
        output.append(next(iter(actions)) if len(actions)==1 else None)
    return tuple(output)


def compile_control(inverse):
    # Data compiled into the function body; neither labels nor a target oracle are captured.
    if len(inverse) != DOMAIN or any(v is not None and (type(v) is not int or not 0<=v<DOMAIN) for v in inverse):
        raise ValueError('inverse outside scope')
    source = 'def control(delta):\n    return ' + repr(tuple(inverse)) + '[delta % 5]\n'
    namespace={'__builtins__':{}}
    exec(compile(source,'<evidence-derived-control>','exec'),namespace)
    fn=namespace['control']; fn.source=source
    return fn


class Queen(LegacyQueen):
    """Same M41 object and ledger; a new controller is evidence-gated, not added to scores."""
    def __init__(self, method='library'):
        if method not in METHODS: raise ValueError('unknown method')
        super().__init__('plain' if method=='plain' else 'library')
        self.strategy=method
        self.policies={}
        self.scopes={}
        self.epoch_start={}
        self.last_control_model={}
        self.active_scene=None
        self.selected=None
        self.control_revision=0
        self.searches=[]
        self.failures=[]
        self.phase=0
        self._component_boot=True
        self._same_identity=id(self)
        self._same_book=id(self.book)

    def bootstrap_components(self):
        # Reuses actual M12 normalisation and M41 dependency/rollback gate on the initial world.
        report=super().review(0,True)
        if report['status']!='accepted':raise RuntimeError('initial component calibration failed')
        self._component_boot=False
        return report

    def valid(self):
        if self._component_boot: return super().valid()
        if not super().valid() or self.selected is None: return False
        policy=self.policies.get(self.active_scene)
        return (policy is self.selected and policy['certificate'] not in self.book.ledger.invalid
                and policy['function'] is policy['bound'] and self._judge is policy['judge_binding'])

    def activate(self, scene, phase):
        self.active_scene=scene;self.phase=phase;self.book.clock=phase
        policy=self.policies.get(scene)
        self.selected=policy
        if policy is not None and policy['certificate'] in self.book.ledger.invalid:
            self.selected=None
        return self.valid()

    def invalidate_control(self, reason, refs=()):
        scene=self.active_scene
        policy=self.policies.get(scene)
        if policy and policy['scope'] not in self.book.ledger.invalid:
            self.book.revoke(policy['scope'],reason)
        self.book.append('control_counterevidence','queen',{'scene':scene,'reason':reason},refs=tuple(refs))
        self.epoch_start[scene]=len(self.book.ledger.records)
        self.selected=None

    def _retrieve(self, budget):
        """No caller-supplied witness. Query the persistent book by current visible scene/scope.
        A shared acquisition interval links local and external clocks, not the anonymous author.
        """
        scene=self.active_scene; floor=self.epoch_start.get(scene,0)
        intentions={};observations={};scanned=[]
        for rec in self.book.ledger.records:
            budget.charge('ops')  # Metadata scan counts, including irrelevant contexts.
            if rec.seq < floor or rec.kind not in ('explore_intention','anonymous_effects'):continue
            payload=json.loads(rec.body)['data']
            if payload['scene']!=scene:continue
            if rec.seq in self.book.ledger.invalid:continue
            budget.charge('reads');budget.charge('bytes',len(rec.body.encode()))
            scanned.append(rec.seq)
            value=json.loads(canonical(payload)) if self.strategy=='plain' else payload
            interval=value['interval']  # Common to all paths: no owner-specific key.
            if rec.kind=='explore_intention':intentions.setdefault(interval,[]).append((rec.seq,value))
            else:observations[interval]=(rec.seq,value)
        groups=[]
        for interval,(obs_id,obs) in observations.items():
            local=intentions.get(interval,[])
            commands=[(p['object'],p['command']) for _,p in local]
            if len(commands)!=len(obs['packet']['paths'][0]):continue
            groups.append((interval,commands,obs['packet'],[k for k,_ in local]+[obs_id]))
        groups.sort(key=lambda g:g[3][-1])
        if self.strategy=='recent':groups=groups[-1:]
        return groups,scanned

    def infer(self,budget):
        groups,read_refs=self._retrieve(budget)
        surviving=set(MODELS); detail=[];supports=[]
        for interval,commands,packet,refs in groups:
            if self.strategy=='masked':pairs=[(i,m) for i in range(3) for m in MODELS]
            else:pairs=fit_pairs(commands,packet,MODELS,budget)
            by_source={i:{m for p,m in pairs if p==i} for i in range(3)}
            union=set(m for _,m in pairs)
            if self.strategy=='pooled':
                # Strong fail-closed source-agnostic pooling; does not fabricate a wrong optimum.
                union=set.intersection(*(by_source[i] for i in range(3)))
            surviving &= union
            detail.append({'interval':interval,'compatible_pairs':[[p,list(m)] for p,m in pairs],
                           'source_options':sorted(set(p for p,m in pairs)), 'evidence':refs})
            supports.extend(refs)
        # Marginal comparator performs same inference without persisting identity as a state variable.
        # It is intentionally strong, not a disadvantaged baseline.
        result={'models':[list(m) for m in sorted(surviving)],'groups':detail,'read_refs':read_refs,
                'supports':sorted(set(supports)),'inverse':list(common_inverse(surviving))}
        if self.strategy!='marginal':self.identity_beliefs.append(result)
        return result

    def _choose_probe(self, models, issued):
        used=Counter(a for _,a in issued)
        if self.strategy=='fixed_probe':return (1,2,3,4,0,1,2,3)[len(issued)]
        models=models or MODELS
        scores=[]
        for a in range(DOMAIN):
            groups=Counter(m[a] for m in models)
            disagreement=len(models)**2-sum(n*n for n in groups.values())
            scores.append((disagreement, -used[a], -a,a))
        return max(scores)[-1]

    def learn(self,port):
        budget=Budget();scene=self.active_scene
        interval=port.open_interval() # Opaque common synchronisation clock, no path index.
        issued=[];attempts=[]
        result=self.infer(budget)
        while budget.probes<budget.max_probes:
            if attempts and all(a is not None for a in result['inverse']):break
            command=self._choose_probe([tuple(m) for m in result['models']],issued)
            obj=len(issued)%2
            prior=self.last_control_model.get(scene)
            ref=self.book.append('explore_intention','queen',{'scene':scene,'interval':interval,
                'object':obj,'command':command,'prediction':None if prior is None else prior[command]})
            issued.append((obj,command))
            budget.charge('probes')
            packet=sensory_projection(port.probe(obj,command))
            obs=self.book.append('anonymous_effects','workers',{'scene':scene,'interval':interval,'packet':packet})
            result=self.infer(budget)
            attempts.append({'command':command,'object':obj,'intent':ref,'observation':obs,
                             'models':result['models'],'inverse':result['inverse'],
                             'source_options':[g['source_options'] for g in result['groups']]})
            if not result['models']:
                # No consistent history: retain the old record and reopen only this context.
                # Exclude earlier groups, but retain the entire actual current experiment.
                current_refs=[k for k in result['supports'] if
                              json.loads(self.book.ledger.records[k].body)['data'].get('interval')==interval]
                if current_refs:
                    self.epoch_start[scene]=min(current_refs)
                    result=self.infer(budget)
        review=self.book.append('source_model_review','queen',{'scene':scene,'attempts':attempts,
            'result':result,'cost':budget.export()},refs=tuple(result['read_refs']))
        models=tuple(tuple(m) for m in result['models'])
        inverse=common_inverse(models)
        allowed=bool(models) and self.strategy!='no_revision'
        if allowed:
            scope=self.book.append('control_scope','queen',{'scene':scene,'models':result['models'],
                'assumptions':['stationary within scene until contradicted','zero-preserving bijection on Z5',
                               'one of three observed paths is driven by the efference journal'],
                'inverse':list(inverse)},refs=(review,),deps=tuple(result['supports']))
            certificate=self.book.append('control_permission','queen',{'scene':scene,'scope':'only unanimous actions'},
                                         refs=(review,),deps=(scope,self.assumption))
            fn=compile_control(inverse)
            self.control_revision+=1
            self.policies[scene]={'scope':scope,'certificate':certificate,'function':fn,'bound':fn,
                'judge_binding':self._judge,'inverse':inverse,'models':models,'review':review,
                'representation':'linear' if len(models)==1 and models[0] in LINEAR else 'finite_permutation_table'}
            self.selected=self.policies[scene]
            if len(models)==1:self.last_control_model[scene]=models[0]
        else:self.selected=None
        record={'review':review,'models':result['models'],'groups':result['groups'],
                'inverse':list(inverse),'attempts':attempts,'cost':budget.export(),
                'adopted':allowed,'complete':all(a is not None for a in inverse),
                'revision':self.control_revision,'scene':scene,'interval':interval}
        self.searches.append(record)
        return record

    def decide(self,packet,remember=True):
        if self._component_boot:return super().decide(packet,remember)
        if not self.valid():raise NotLicensed('no current source-grounded action licence')
        return JudgeQueen.decide(self,packet,remember)

    def predict(self,packet):return self.decide(packet,False)

    def act(self,obj,target,tick,future=False):
        # Physical trial port is the same one attached at construction; all public task entries gate.
        if not self.valid():return {'executed':False,'command':None,'reason':'invalid_scope'}
        views=self._port.sense();positions=views[0]['decoded']
        packet=packet_from_views(positions,self.last_views,obj,tick)
        d=self.decide(packet);self.last_views=positions
        if d.value.denominator!=1:return {'executed':False,'command':None,'reason':'unsupported_judgment'}
        delta=(target-int(d.value))%DOMAIN
        command=self.selected['function'](delta)
        if command is None:return {'executed':False,'command':None,'reason':'no_common_action'}
        ref=self.book.append('controlled_intention','queen',{'scene':self.active_scene,'object':obj,
             'target':target,'position':int(d.value),'delta':delta,'command':command,
             'control_revision':self.control_revision},deps=(self.selected['certificate'],))
        out=self._port.move(obj,command)
        return {'executed':True,'command':command,'delta':delta,'intent':ref,'result':out}

    def execute(self,obj,target,tick):return self.act(obj,target,tick)

    def receive_feedback(self,success):
        if not success:
            old=self.selected
            self.failures.append({'scene':self.active_scene,'phase':self.phase,'revision':self.control_revision})
            self.invalidate_control('future task contradicts current control interpretation',
                                    () if old is None else (old['review'],))
