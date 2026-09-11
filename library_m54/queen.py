"""Continuous Queen: mismatch from own efference and Worker observations only.
Uses unchanged M8 Ledger. Task truth, author labels and hidden regime numbers are absent.
"""
from collections import Counter
from random import Random
from dataclasses import dataclass
import json
from .grammar import P,TRAIN,STATES,infer,choose,predict,compile_tree,show,splits
from library_m8.core import Ledger

METHODS=('library','plain','fixed','table','no_history','no_structure')

def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def arithmetic():
    ns={'__builtins__':{}};exec('def emit(x):\n    return x % 7\n',ns);return ns['emit']

class NotLicensed(PermissionError):pass
class Limit(RuntimeError):pass

@dataclass
class Budget:
    probes:int=0
    reads:int=0
    bytes:int=0
    ops:int=0
    def charge(self,k,n=1):
        lim={'probes':180,'reads':5000,'bytes':5000000,'ops':12000000}[k]
        if getattr(self,k)+n>lim:raise Limit(k)
        setattr(self,k,getattr(self,k)+n)
    def export(self):return dict(probes=self.probes,reads=self.reads,bytes=self.bytes,ops=self.ops)

class Queen:
    def __init__(self,seed=0,method='library'):
        if method not in METHODS:raise ValueError('method')
        self.method=method;self.ledger=Ledger();self.birth=id(self);self.book_birth=id(self.ledger)
        self._emit=arithmetic();self.offsets=None;self.calibration=None
        self.tree=None;self.function=None;self.bound=None;self.scope=None;self.permission=None
        self.version=0;self.last=0;self.pending=None;self.floor=0
        self.pairs=[];self.revisions=[];self.failures=[];self.component_changes=[];self.retrospectives=[]
        self.cost=Counter();self.order=list(TRAIN);Random(seed^19909).shuffle(self.order)
        self.decisions=[];self.identity=[];self.rejections=[]
    def add(self,kind,data,refs=(),deps=()):
        return self.ledger.add(kind,'Queen' if kind!='observation' else 'Workers',data,
            refs=tuple(dict.fromkeys(refs)),deps=tuple(dict.fromkeys(deps)))
    def read(self,k,budget=None):
        if k in self.ledger.invalid:raise NotLicensed('withdrawn evidence')
        r=self.ledger.records[k]
        self.cost['actual_record_reads']+=1;self.cost['actual_record_bytes']+=len(r.body.encode())
        if budget:budget.charge('reads');budget.charge('bytes',len(r.body.encode()))
        v=json.loads(r.body)
        return json.loads(canonical(v)) if self.method=='plain' else v
    def valid(self):
        return (self.permission is not None and self.permission not in self.ledger.invalid
                and self.calibration is not None and self.calibration not in self.ledger.invalid
                and self.function is not None and self.function is self.bound)
    def invalidate(self,why,refs=()):
        if self.scope is not None and self.scope not in self.ledger.invalid:self.ledger.revoke(self.scope,why)
        r=self.add('mismatch',{'reason':why,'version':self.version},refs)
        self.failures.append(r)
    def decode(self,packet,offset=None):
        if set(packet)!={'workers'}:raise ValueError('only observed Worker fields allowed')
        rows=packet['workers']
        if len(rows)!=2 or any(len(v)!=2 or any(type(x)is not int or not 0<=x<7 for x in v) for v in rows):
            raise ValueError('invalid observations')
        off=self.offsets if offset is None else offset
        if off is None:raise NotLicensed('no calibration')
        return [[(x-off[j])%7 for x in v] for j,v in enumerate(rows)]
    def calibrate(self,port,b):
        refs=[];results=[];old=self.offsets
        for a in (0,3):
            b.charge('probes');r=port.calibrate(a)
            if set(r)!={'anchor','readings'} or r['anchor']!=a:raise ValueError('calibration schema')
            refs.append(self.add('calibration_observation',r));results.append(r)
        off=results[0]['readings']
        if any((results[1]['readings'][j]-3)%7!=off[j] for j in range(2)):
            self.invalidate('calibration violates additive assumption',refs);return False
        if old!=off or self.calibration is None or self.calibration in self.ledger.invalid:
            if self.calibration is not None and self.calibration not in self.ledger.invalid:self.ledger.revoke(self.calibration,'recalibration')
            self.offsets=off[:]
            self.calibration=self.add('calibration_permission',{'offsets':off,'scope':'stable additive sensors until contradicted'},deps=refs)
            if old is not None:self.component_changes.append({'component':'Workers','before':old,'after':off,'evidence':refs})
        b.charge('probes');actual=[self._emit(a) for a in (1,2)]
        k=self.add('own_judgment_probe',{'inputs':[1,2],'actual':actual})
        if actual!=[1,2]:
            oldfn=self._emit;self._emit=arithmetic()
            self.component_changes.append({'component':'own_emission','real_binding_changed':oldfn is not self._emit,'evidence':[k]})
        return True
    def prepare(self,port,s):
        p,o,obj,h=s;actual=self._emit(h)
        i=self.add('primer_intention',{'object':1-obj,'requested':h,'issued':actual})
        after=port.move(1-obj,actual,'primer');self.last=actual
        self.add('primer_observation',after,refs=(i,))
        positions=[0,0];positions[obj]=p;positions[1-obj]=o
        return port.place(positions)
    def sample(self,i,o,b=None):
        a=self.read(i,b);z=self.read(o,b)
        if z['intention']!=i:raise ValueError('unpaired evidence')
        before=self.decode(a['before'],a['offsets']);after=self.decode(z['after'],a['offsets'])
        obj=a['object'];cmd=a['issued']
        if before[0]!=before[1] or after[0]!=after[1] or before[0][1-obj]!=after[0][1-obj] or not cmd:return None
        gain=(after[0][obj]-before[0][obj])*pow(cmd,-1,7)%7
        if not gain:return None
        return {'state':[before[0][obj],before[0][1-obj],obj,a['last']], 'gain':gain,'command':cmd,'evidence':[i,o]}
    def trial(self,port,obj,requested,mode,b=None,choice=None):
        before=port.sense();decoded=self.decode(before);state=(decoded[0][obj],decoded[0][1-obj],obj,self.last)
        issued=self._emit(requested)
        predicted=None if self.function is None else self.function(*state,issued)
        prior_positions=None if predicted is None else [(decoded[0][j]+(predicted if j==obj else 0))%7 for j in range(2)]
        i=self.add('intention',{'object':obj,'before':before,'offsets':self.offsets[:],
            'state':list(state),'last':self.last,'requested':requested,'issued':issued,'predicted_after':prior_positions,
            'model':self.tree,'version':self.version,'mode':mode,'choice':choice},
            refs=(() if self.permission is None else (self.permission,)))
        after=port.move(obj,issued,mode);self.last=issued
        o=self.add('observation',{'after':after,'intention':i},refs=(i,));self.pairs.append((i,o))
        s=self.sample(i,o,b)
        mismatch=(issued!=requested or self.decode(before)[0]!=self.decode(before)[1] or
                  self.decode(after)[0]!=self.decode(after)[1] or
                  (prior_positions is not None and any(row!=prior_positions for row in self.decode(after))))
        if mode=='task' and mismatch:
            self.invalidate('own command or Worker observations contradict prediction',(i,o));self.pending=(i,o)
        return {'intention':i,'observation':o,'sample':s,'mismatch':mismatch,'issued':issued,'requested':requested}
    def retrieve(self,b):
        data=[]
        for i,o in self.pairs:
            b.charge('ops')
            if i<self.floor or i in self.ledger.invalid or o in self.ledger.invalid or self.method=='no_history':continue
            s=self.sample(i,o,b)
            if s:data.append(s)
        return data
    def repair(self,port):
        repair_start=len(self.ledger.records);retested=set()
        b=Budget();oldtree=self.tree;oldperm=self.permission;oldoff=None if self.offsets is None else self.offsets[:]
        c0=len(self.component_changes)
        if not self.calibrate(port,b):return {'status':'observation_reject','cost':b.export()}
        seeds=[]
        if self.pending:
            old=self.read(self.pending[0],b);obj=old['object'];decoded=self.decode(old['before'])
            s=(decoded[0][obj],decoded[0][1-obj],obj,old['last'])
            self.prepare(port,s);b.charge('probes')
            e=self.trial(port,obj,max(1,old['requested']),'probe',b,{'why':'repeat old failure after separating sensor/own faults'})
            if e['sample']:seeds=[e['sample']]
            component_only=(len(self.component_changes)>c0 and seeds and predict(oldtree,s)==seeds[0]['gain'])
            if not component_only:self.floor=e['intention']
        data=self.retrieve(b);keys={tuple(r['evidence']) for r in data}
        data += [r for r in seeds if tuple(r['evidence']) not in keys]
        history_n=len(data);seen={tuple(r['state']) for r in data};trace=[];stable=0;signature=None
        models=[];status='budget_exhausted';candidate=None;validations=[]
        def incorporate(row):
            nonlocal data,seen,stable,history_n
            conflicts=[r for r in data if r['state']==row['state'] and r['gain']!=row['gain']]
            if conflicts:
                self.add('applicability_conflict',{'old':conflicts,'new':row,'decision':'reopen current interval, preserve old evidence'},
                         refs=tuple(k for r in conflicts+[row] for k in r['evidence']))
                self.invalidate('same observed condition now has a different effect',tuple(row['evidence']))
                self.floor=row['evidence'][0];data=[];seen=set();stable=0;history_n=0
            data.append(row);seen.add(tuple(row['state']))
        try:
            for step in range(180):
                if self.method=='no_structure':
                    labels={r['gain'] for r in data};models=[('gain',next(iter(labels)))] if len(labels)==1 else []
                    if len(labels)>1:status='detected_structure_inadequate';break
                elif self.method=='table':models=[]
                else:models=infer([(r['state'],r['gain']) for r in data],b.charge)
                if not models and data and history_n and self.method not in ('table','no_structure'):
                    older=[r for r in data if r['evidence'][0]<repair_start and r['evidence'][0] not in retested]
                    if older:
                        target=data[-1]['state']
                        previous=max(older,key=lambda r:sum(a==c for a,c in zip(r['state'],target)))
                        retested.add(previous['evidence'][0]);state=tuple(previous['state'])
                        b.charge('probes');self.prepare(port,state)
                        replay=self.trial(port,state[2],1,'probe',b,{'why':'retest historical applicability after no consistent conditional tree','old_evidence':previous['evidence']})
                        if replay['sample']:incorporate(replay['sample'])
                        continue
                sig=repr(models[0]) if models else None
                stable=stable+1 if sig is not None and sig==signature else 0;signature=sig
                ready=(b.probes>=32 and stable>=12) or (self.method=='table' and b.probes>=64) or (oldtree is None and history_n>=40 and bool(models))
                if ready:
                    candidate=models[0] if models else None
                    if self.method=='table':status='candidate';break
                    # Candidate fixed before these further observations. Reject on first counterexample.
                    passed=True;val=[]
                    # Choose isolating interventions from the proposed expression, not hidden labels.
                    contrasts=[]
                    for axis in (1,2,3):
                        pair=None
                        for a in self.order:
                            for newvalue in (range(2) if axis==2 else range(7)):
                                z=list(a);z[axis]=newvalue;z=tuple(z)
                                if predict(candidate,a)!=predict(candidate,z):pair=(a,z);break
                            if pair:break
                        if pair:
                            contrasts.extend([(pair[0],1,axis),(pair[1],1,axis),(pair[0],2,axis)])
                    for state,command,axis in contrasts:
                        self.prepare(port,state);b.charge('probes')
                        e=self.trial(port,state[2],command,'validation',b,{'why':'hold command fixed and change one raw condition, then vary command','axis':axis})
                        row=e['sample'];val.append({'expected':predict(candidate,state),'actual':None if row is None else row['gain'],'evidence':[] if row is None else row['evidence'],'contrast_axis':axis,'command':command,'state':list(state)})
                        if row:incorporate(row)
                        if row is None or predict(candidate,state)!=row['gain']:passed=False;break
                    for j in range(12 if passed else 0):
                        state=next((s for s in self.order if s not in seen),None)
                        if state is None:break
                        self.prepare(port,state);b.charge('probes')
                        result=self.trial(port,state[2],1+j%6,'validation',b,{'why':'adoption test for fixed candidate'})
                        seen.add(state)
                        row=result['sample'];val.append({'expected':predict(candidate,state),'actual':None if row is None else row['gain'],'evidence':[] if row is None else row['evidence']})
                        if row:incorporate(row)
                        if row is None or predict(candidate,state)!=row['gain']:passed=False;break
                    validations.append({'candidate':candidate,'observations':val,'accepted':passed})
                    if passed:status='candidate';break
                    self.rejections.append({'candidate':candidate,'counterexample':val[-1]});stable=0
                    continue
                if self.method in ('fixed','table'):
                    state=next((s for s in self.order if s not in seen),None);choice={'why':'fixed acquisition order'}
                else:state,choice=choose(models,self.order,seen,b.charge)
                if state is None:break
                b.charge('probes');self.prepare(port,state)
                command=1+len(data)%6;e=self.trial(port,state[2],command,'probe',b,choice)
                seen.add(state)
                if e['sample']:incorporate(e['sample'])
                trace.append({'state':list(state),'command':command,'sample':e['sample'],'model_before':models[0] if models else None,'choice':choice})
            if status=='candidate':
                if self.method=='table':
                    table={tuple(r['state']):r['gain'] for r in data}
                    while len(canonical([[list(s),g] for s,g in table.items()]).encode())>2048:del table[next(iter(table))]
                    self.table=table;fn=lambda p,o,j,h,a:None if (p,o,j,h) not in table else table[p,o,j,h]*a%7
                    src=canonical([[list(s),g] for s,g in table.items()]);candidate=('gain',1)
                else:fn=compile_tree(candidate);src=fn.source
                if len(src.encode())>2048:raise Limit('deployment_bytes')
                support=list(dict.fromkeys(k for row in data for k in row['evidence']))
                collision=None
                for x in data:
                    for y in data:
                        b.charge('ops')
                        if x['command']==y['command'] and x['gain']!=y['gain']:
                            collision={'first':x['evidence'],'second':y['evidence'],'same_command':x['command'],'gains':[x['gain'],y['gain']]};break
                    if collision:break
                r=self.add('model_revision',{'old':oldtree,'new':candidate,'source':src,'history_used':history_n,
                    'trace':trace,'validation':validations,'cost':b.export(),
                    'falsifier':'new calibrated before/after effect inconsistent with committed prediction',
                    'same_command_conflicting_effects':collision,
                    'constant_gain_explanation_refuted':len(set(r['gain'] for r in data))>1,
                    'diagnostic_components':[r['component'] for r in self.component_changes[c0:]],
                    'new_conditions':predicate_signature(candidate)},
                    refs=tuple(support)+(() if oldperm is None else (oldperm,)))
                self.scope=self.add('action_model_assumption',{'family':'data-built conditional gain, depth<=3; stationary until contradicted'},deps=support)
                self.permission=self.add('task_permission',{'model':candidate,'source':src},refs=(r,),deps=(self.scope,self.calibration))
                self.tree=candidate;self.function=self.bound=fn;self.pending=None;self.version+=1
                row={'status':'adopted','version':self.version,'old':oldtree,'new':candidate,
                    'actual_update':(oldtree is not None and any(predict(oldtree,s)!=predict(candidate,s) for s in STATES)) or len(self.component_changes)>c0,
                    'structural_change':oldtree is not None and predicate_signature(oldtree)!=predicate_signature(candidate),
                    'splits':splits(candidate),'history_used':history_n,'support':support,'review':r,
                    'source':src,'bytes':len(src.encode()),'cost':b.export(),'validation':validations}
                self.revisions.append(row);self.cost.update(b.export());return row
        except Limit as e:status='budget:'+str(e)
        self.function=self.bound=None;self.cost.update(b.export())
        self.add('unresolved',{'reason':status,'trace':trace,'cost':b.export()})
        return {'status':status,'cost':b.export()}
    def decide(self,before,obj,goal):
        if not self.valid():raise NotLicensed('invalid permission')
        decoded=self.decode(before)
        if decoded[0]!=decoded[1]:raise NotLicensed('Workers disagree')
        state=(decoded[0][obj],decoded[0][1-obj],obj,self.last)
        for a in range(7):
            self.cost['task_comparisons']+=1
            if self.function(*state,a)==(goal-state[0])%7:return a
        raise NotLicensed('no supported action')
    def act(self,port,obj,goal):
        before=port.sense()
        try:a=self.decide(before,obj,goal)
        except NotLicensed as e:return {'executed':False,'reason':str(e)}
        return dict(self.trial(port,obj,a,'task'),executed=True)
    execute=act
    def reinterpret(self):
        rows=[]
        for i,o in self.pairs:
            if i in self.ledger.invalid or o in self.ledger.invalid:continue
            old=self.read(i);actual=self.sample(i,o)
            if actual is None or old['predicted_after'] is None:continue
            newgain=predict(self.tree,tuple(actual['state']))
            if old['predicted_after']!=self.decode(self.read(o)['after'],old['offsets'])[0]:
                rows.append({'intention':i,'observation':o,'then_predicted':old['predicted_after'],
                    'observed_gain':actual['gain'],'later_gain':newgain,'later_explains':newgain==actual['gain'],
                    'qualification':'original physics can belong to an earlier applicability interval'})
            if len(rows)>=12:break
        r=self.add('retrospective',{'version':self.version,'rows':rows},refs=tuple(k for row in rows for k in (row['intention'],row['observation'])))
        self.retrospectives.append(r);return rows
    def attribute(self,intent,packet):
        if set(packet)!={'paths'} or len(packet['paths'])!=2:raise ValueError('anonymous schema')
        own=self.read(intent);receipts=[o for i,o in self.pairs if i==intent and o not in self.ledger.invalid]
        after=self.read(receipts[-1])['after'] if receipts else None;options=[]
        for j,p in enumerate(packet['paths']):
            if set(p)!={'before','after'}:raise ValueError('forbidden identity metadata')
            if p['before']==own['before'] and p['after']==after:options.append(j)
        probs=[1/len(options) if j in options else 0 for j in range(2)] if options else [None,None]
        r={'options':options,'probabilities':probs,'scope':'trusted own receipt and two candidate histories'}
        self.add('attribution',r,refs=(intent,));self.identity.append(r);return r


def predicate_signature(t):
    if t is None or t[0]=='gain':return ()
    return (canonical(t[1]),predicate_signature(t[2]),predicate_signature(t[3]))
