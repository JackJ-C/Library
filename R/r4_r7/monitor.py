"""Second-order prediction of the Queen's actual approximate planning errors.
Training targets are computed from paired Worker observations, not evaluator `correct`.
The scaffold, confidence bins and checking budget are designed, not self-invented.
"""
from dataclasses import dataclass
import copy
from types import MethodType
import json
from random import Random
from collections import defaultdict
from library_m54.world import World, Port


def feature_key(trace):
    if set(trace)!={'repeats','margin'}:raise ValueError('only introspectively available fields')
    m=trace['margin']
    return (trace['repeats'],sum(m>t for t in (.20,.55,1.1)))

class ReliabilityModel:
    def __init__(self):
        self.counts=defaultdict(lambda:[1,2]);self.support=[];self.total=[1,2]
    def observe(self,trace,consistent,key):
        cell=self.counts[feature_key(trace)];cell[0]+=int(consistent);cell[1]+=1
        self.total[0]+=int(consistent);self.total[1]+=1
        self.support.append(key)
    def probability(self,trace):
        a,n=self.counts.get(feature_key(trace),[1,2]);return a/n
    def export(self):return {'cells':[[*k,*v] for k,v in sorted(self.counts.items())],
                             'global':self.total[:],'support':self.support[:]}

def fast_plan(q,positions,obj,goal,repeats,rng,donor=False):
    """A real stochastic fast planner; monitor sees margin, not true loss.
    Independent numerical perturbations represent an explicitly designed approximate
    computation, not measurement noise or phenomenological experience.
    """
    effect=q.self_options[0]*q.tree[1]%7;p=positions[obj]
    # Donor's speed/precision tradeoff is different; no donor id goes into the fitted function.
    sigma=(.65 if repeats==1 else 3.7) if donor else 2.8
    scores=[]
    for a in range(7):
        residual=(p+effect*a-goal)%7;distance=min(residual,7-residual)
        val=distance+sum(rng.uniform(-sigma,sigma) for _ in range(repeats))/repeats
        scores.append(val)
    order=sorted(range(7),key=lambda a:(scores[a],a))
    return order[0],{'repeats':repeats,'margin':scores[order[1]]-scores[order[0]]},scores

def behavior_receipt(q,world,positions,obj,goal,action,trace,prob=None,mode='train'):
    world.place(positions);before=Port(world).sense()
    i=q.add('R6_planning_intention',{'before':before,'object':obj,'goal':goal,'request':action,
                                   'inner_trace':trace,'prospective_confidence':prob,'offsets':q.offsets[:],'mode':mode})
    issued=q._emit(action);after=Port(world).move(obj,issued,'R6_planning')
    o=q.add('R6_planning_observation',{'after':after,'issued':issued},refs=(i,))
    decoded=q.decode(after)
    consistent=decoded[0]==decoded[1] and decoded[0][obj]==goal
    # This is a theory-scoped sensory check, not hidden task truth.
    judge=q.add('R6_own_error_check',{'predicted_goal':goal,'decoded':decoded,
                                   'consistent':consistent},refs=(i,o),deps=(o,q.calibration))
    return consistent,judge,issued,after

def auc(probs,correct):
    pos=[p for p,c in zip(probs,correct) if c];neg=[p for p,c in zip(probs,correct) if not c]
    if not pos or not neg:return None
    return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))

def rebuild_model(q,keys):
    model=ReliabilityModel()
    for key in keys:
        check=q.ledger.records[key]
        i,o=check.refs
        intent=q.read(i);obs=q.read(o)
        before=q.decode(intent['before'],intent['offsets'])
        after=q.decode(obs['after'],intent['offsets'])
        consistent=before[0]==before[1] and after[0]==after[1] and after[0][intent['object']]==intent['goal']
        model.observe(intent['inner_trace'],consistent,key)
    return model


def current_reliability(q,trace):
    key=getattr(q,'monitor_ref',None)
    if key is None or key in q.ledger.invalid or q.monitor is not getattr(q,'monitor_bound',None):return {'status':'unknown','probability':None}
    return {'status':'supported','probability':q.monitor.probability(trace),'model':key}

def assay(q,world,seed,ntrain=256,ntest=128,checks=32):
    rng=Random(seed);model=ReliabilityModel();other=ReliabilityModel();train=[];evalrows=[];donor_rows=[]
    q.approximate_plan=MethodType(fast_plan,q)
    for j in range(ntrain):
        positions=[rng.randrange(7),rng.randrange(7)];obj=rng.randrange(2);goal=rng.randrange(7)
        repeats=rng.choice((1,3))
        action,trace,scores=q.approximate_plan(positions,obj,goal,repeats,rng)
        p=model.probability(trace)
        ok,key,issued,after=behavior_receipt(q,world,positions,obj,goal,action,trace,p)
        model.observe(trace,ok,key)
        # A distinct computation stream in a matched copy, used only to train a transplant control.
        a,t,_=fast_plan(q,positions,obj,goal,repeats,rng,True)
        donor=copy.deepcopy(world);donor.place(positions);issued_other=q._emit(a)
        donor_obs=Port(donor).move(obj,issued_other,'R6_donor_control')
        decoded_other=q.decode(donor_obs)
        other_ok=decoded_other[0]==decoded_other[1] and decoded_other[0][obj]==goal
        other.observe(t,other_ok,j)
        donor_rows.append([positions,obj,goal,t,a,issued_other,donor_obs['workers'],other_ok])
        train.append([positions,obj,goal,repeats,trace['margin'],action,issued,after['workers'],ok,key])
    rebuilt=rebuild_model(q,model.support)
    if rebuilt.export()!=model.export():raise AssertionError('raw history and cached reliability differ')
    model=rebuilt;q.monitor=model
    modelref=q.add('R6_current_metacognitive_model',model.export(),deps=tuple(model.support))
    q.monitor_ref=modelref;q.monitor_bound=model
    before_fn=q.action_program;before_emit=q._emit;before_obj=id(q)
    for j in range(ntest):
        positions=[rng.randrange(7),rng.randrange(7)];obj=rng.randrange(2);goal=rng.randrange(7)
        repeats=rng.choice((1,3));action,trace,scores=q.approximate_plan(positions,obj,goal,repeats,rng)
        # Save before any outcome; test rows never update the monitor or select models.
        prediction=current_reliability(q,trace)
        if prediction['status']!='supported':raise PermissionError('metacognitive support missing')
        probs={'own':prediction['probability'], 'blind':model.total[0]/model.total[1],
               'transplant':other.probability(trace), 'restored':model.probability(trace),
               'renamed':model.probability(trace), 'fixed':1.0 if repeats==3 else 0.0}
        rec=q.add('R6_confidence_test_forecast',{'positions':positions,'object':obj,'goal':goal,
            'raw_action':action,'trace':trace,'probabilities':probs},refs=(modelref,))
        evalrows.append({'positions':positions,'object':obj,'goal':goal,'fast_action':action,
                         'trace':trace,'scores':scores,'probabilities':probs,'forecast':rec})
    # The same quota in all arms. All raw first-order answers above are fixed and matched.
    ties=list(range(ntest));rng.shuffle(ties);tieindex={j:i for i,j in enumerate(ties)}
    arms={}
    for arm in ('own','blind','transplant','restored','renamed','fixed','always_check','never_check'):
        selected=set(range(ntest)) if arm=='always_check' else set() if arm=='never_check' else set(
            sorted(range(ntest),key=lambda j:(evalrows[j]['probabilities'][arm],tieindex[j]))[:checks])
        output=[];raw_correct=[];ps=[]
        for j,r in enumerate(evalrows):
            p,o,g=r['positions'],r['object'],r['goal']
            # Same actual q emitter, same model and planner. Only monitor-directed checking differs.
            requested=r['fast_action']
            if j in selected:
                decoded={'workers':[[ (x+q.offsets[w])%7 for x in p] for w in range(2)]}
                requested=q.decide(decoded,o,g)
            raw_trial=copy.deepcopy(world);raw_trial.place(p);raw_trial.move(o,q._emit(r['fast_action']),'R6_raw')
            raw_final=raw_trial.positions[o]
            trial=copy.deepcopy(world);trial.place(p);trial.move(o,q._emit(requested),'R6_assay')
            final=trial.positions[o]
            output.append([requested,final,final==g]);raw_correct.append(raw_final==g)
            if arm in r['probabilities']:ps.append(r['probabilities'][arm])
        arms[arm]={'checked':sorted(selected),'outputs':output,'correct':sum(r[2] for r in output),
                   'raw_correct':sum(raw_correct),'raw_total':len(raw_correct),
                   'brier':sum((p-int(c))**2 for p,c in zip(ps,raw_correct))/ntest if ps else None,
                   'type2_auc':auc(ps,raw_correct) if ps else None}
    # Replay selected primary requests physically, with raw sensory outcomes and no monitor updates.
    primary=[]
    for j,r in enumerate(evalrows):
        request=arms['own']['outputs'][j][0]
        ok,key,issued,after=behavior_receipt(q,world,r['positions'],r['object'],r['goal'],request,
                                           r['trace'],r['probabilities']['own'],'test_live')
        if ok!=arms['own']['outputs'][j][2]:raise AssertionError('physical replay differs')
        primary.append([key,issued,after['workers'],ok])
    assert before_fn is q.action_program and before_emit is q._emit and id(q)==before_obj
    return {'train':train,'own_model':model.export(),'other_model':other.export(),'test':evalrows,
            'arms':arms,'donor_training':donor_rows,'actual_primary':primary,'model_ref':modelref,'same_first_order_binding':True,
            'cost':{'fast_scalar_scores':7*sum(r[3] for r in train)+7*sum(r['trace']['repeats'] for r in evalrows),
                    'checking_budget':checks,'test_cases':ntest}}
