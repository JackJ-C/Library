"""R4-R7 experiment harness. Evaluation targets never enter learning routines.
All official seeds and thresholds live in the frozen protocol, not outcome-dependent code.
"""
import json,copy
from dataclasses import asdict
from random import Random
from hashlib import sha256
from collections import Counter
from .lifecycle import Queen
from . import search
from .monitor import assay,current_reliability
from src.core import World,Port

METHODS=('recursive','plain','frozen_parent','fixed_query','hand_query')
HAND=('/','info','price')

class Emitter:
    def __init__(self,multiplier,glitch=False):self.multiplier=multiplier;self.glitch=glitch
    def __call__(self,a):return (self.multiplier*a+int(self.glitch and a==3))%7

def make_queen(seed,method='recursive'):
    q=Queen(seed,'plain' if method=='plain' else 'library')
    w=World((0,0,'less',3,[(seed%6)+1,2,3,4]))
    q._emit=Emitter((seed//7)%6+1)
    q.diagnose(Port(w))
    # Preserve a real M54 action before the new diagnostic domain is attached.
    q.step(Port(w),0,(w.positions[0]+1)%7)
    q.search_program=search.Program(HAND if method=='hand_query' else 0)
    return q,w

def p_json(p):return {'masks':[list(x) for x in p.masks],'prices':list(p.prices),'count':p.count}

def own_diagnosis(q,p,body,c):
    q.diagnostic_process=body
    policy=q.search_program
    receipts=[]
    def read(query):
        i=q.add('R5_computation_probe',{'query':query,'program':policy.source})
        value=q.diagnostic_process(query)
        o=q.add('R5_computation_receipt',{'value':value},refs=(i,))
        receipts.append([i,o])
        return value
    cost,H,trace=search.solve(p,read,policy,c,True)
    if H.bit_count()!=1:raise RuntimeError('supported diagnostic basis did not identify behavior')
    # Target for later counterfactual replays comes from inferred observations, not body._h.
    inferred=H.bit_length()-1
    r=q.add('R5_identified_execution',{'inferred':inferred,'price':cost,'steps':trace},
            deps=tuple(o for _,o in receipts))
    return inferred,{'price':cost,'identified':inferred,'steps':trace,'receipts':receipts,'record':r}

def test_program(ast,cases):
    c=search.Cost();total=0;rows=[]
    for p,h in cases:
        cost,H,steps=search.solve(p,search.Body(p,h),search.Program(ast),c)
        if H.bit_count()!=1:raise RuntimeError('held-out not identified')
        total+=cost;rows.append({'price':cost,'steps':steps})
    return total,rows,asdict(c)

def lineage(seed,method='recursive',monitor=True):
    q,w=make_queen(seed,method);qid=id(q);lid=id(q.ledger)
    qstate={'initial_version':q.version,'initial_self':q.current_self(),'world_gain':q.tree[1],'offsets':q.offsets[:]}
    c=search.Cost();history=[];rounds=[]
    cases=[search.make_problem(seed*1000+200+i,n=(24,40,48)[i%3],nq=(18,30)[i%2]) for i in range(32)]
    for generation in range(8):
        live=[]
        for j in range(8):
            p,true=search.make_problem(seed*1000+generation*20+j)
            h,observed=own_diagnosis(q,p,search.Body(p,true),c)
            if h!=true:raise AssertionError('scorer only: wrong inferred signature')
            history.append((p,h));live.append({'problem':p_json(p),'target_evaluator_only':true,'observed':observed})
        train=history[-24:];before=q.search_program
        proposals=search.pool(before.ast,seed*171+generation)
        counter=None;effect=None;primary=None
        if method not in ('fixed_query','hand_query'):
            proposer=search.Program(0) if method=='frozen_parent' else before
            new,primary=search.successor(before.ast,proposer,proposals,train,c)
            cc=search.Cost()
            counter,counter_record=search.successor(before.ast,search.Program(0),proposals,train,cc)
            # Both evaluations use the same observed histories, pool and full-candidate quota.
            if primary['accepted']:
                q.search_program=search.Program(new)
                q.search_history.append(q.search_program.source)
            primary['new_source']=q.search_program.source
            primary['old_source']=before.source
            primary['parent_source']=proposer.source
            primary['actual_rebind']=q.search_program is not before
            record=q.add('R5_search_revision',primary,refs=tuple(v['observed']['record'] for v in live))
            bc,br,bops=test_program(before.ast,cases)
            nc,nr,nops=test_program(q.search_program.ast,cases)
            fc,fr,fops=test_program(counter,cases)
            strict_link=(generation>0 and primary['accepted'] and nc<bc and nc<fc)
            effect={'before':bc,'current':nc,'frozen_parent':fc,'delta':fc-nc,'strict_link':strict_link,
                    'current_replays':nr,'counter_replays':fr,'counter_ast':counter,
                    'counter_search':counter_record,'counter_cost':asdict(cc)}
        else:
            nc,nr,nops=test_program(before.ast,cases)
            effect={'before':nc,'current':nc,'frozen_parent':nc,'delta':0,'strict_link':False,
                    'current_replays':nr}
        rounds.append({'generation':generation,'live':live,'pool':proposals,'primary':primary,
                       'evaluation_only':effect,'policy_ast':q.search_program.ast})
        if id(q)!=qid or id(q.ledger)!=lid:raise AssertionError('Queen or ledger replaced')
    result={'seed':seed,'method':method,'same_queen':True,'initial':qstate,'rounds':rounds,
            'heldout_cases':[{'problem':p_json(p),'target_evaluator_only':h} for p,h in cases],
            'cost':asdict(c),'accepted':len(q.search_history),
            'final_test_cost':rounds[-1]['evaluation_only']['current'],
            'recursive_delta':sum(r['evaluation_only']['delta'] for r in rounds[1:]),
            'strict_links':sum(r['evaluation_only']['strict_link'] for r in rounds[1:])}
    flags=[r['evaluation_only']['strict_link'] for r in rounds]
    result['consecutive_links']=any(a and b for a,b in zip(flags,flags[1:]))
    if monitor and method in ('recursive','plain'):
        result['metacognition']=assay(q,w,seed^0x760329)
        # Old history preserved; confidence claim withdrawn separately from sensor/actuator knowledge.
        m=q.monitor_ref;support=q.monitor.support[0];emission=q.self_permission;cal=q.calibration
        snapshot=q.ledger.records[support].body
        q.ledger.revoke(support,'R6 actual support withdrawal test')
        result['monitor_withdrawal']={'claim_invalid':m in q.ledger.invalid,
            'query_unknown':current_reliability(q,{'repeats':1,'margin':0.3})['status']=='unknown',
            'emission_preserved':emission not in q.ledger.invalid,'calibration_preserved':cal not in q.ledger.invalid,
            'history_unchanged':q.ledger.records[support].body==snapshot}
    result['ledger']=q.ledger.export()  # Every produced record, for every official trajectory.
    result['invalid']=sorted(q.ledger.invalid)
    return result

def stress():
    q,w=make_queen(2);old=q.self_permission;worker=q.calibration;world=q.scope
    # Change within the same callable: not detected via identity or a supplied fault label.
    q._emit.glitch=True
    p=Port(w);before=q.decode(p.sense())[0][0];s=q.self_options[0];g=q.tree[1]
    goal=(before+3*s*g)%7
    r=q.step(p,0,goal)
    observed=q.current_self();hist=q.historical_self(old)
    review=q.diagnose(p)
    out={'nonlinear_self':{'observed_mismatch':r.get('mismatch'), 'current':observed,
         'history_still_readable':bool(hist['record']), 'worker_preserved':worker not in q.ledger.invalid,
         'world_preserved':world not in q.ledger.invalid,'rediagnosis':review['status'],
         'task_stays_closed':not q.r_valid()}}
    q._emit.glitch=False;recover=q.diagnose(p)
    out['nonlinear_self']['recovery_after_condition_removed']=recover['status']=='adopted' and q.r_valid()
    # Pure external drift does not itself prove that the own-emission estimate is false.
    q,w=make_queen(3);old=q.self_permission
    par=list(w.parameters);par[-1]=[q.tree[1]%6+1,2,3,4];w.parameters=tuple(par)
    p=Port(w);position=q.decode(p.sense())[0][0];q.step(p,0,(position+1)%7)
    out['external_drift']={'task_closed':not q.r_valid(),'own_claim_not_revoked':old not in q.ledger.invalid,
                          'own_query_supported':q.current_self()['status']=='supported'}
    # Archived authorship is not inferred from successful control.
    q,w=make_queen(4);i,o=q.pairs[-1];intent=q.read(i);observed=q.read(o)['after']
    path={'before':intent['before'],'after':observed}
    out['indistinguishable_authorship']=q.attribute(i,{'paths':[path,copy.deepcopy(path)]})
    out['scope']='arithmetic, custody, introspection port, scoring grammar and test constructor remain trusted'
    return out

def bootstrap_mean(values,seed=4019,reps=4000):
    rng=Random(seed);n=len(values)
    vals=sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(reps))
    return [vals[int(.025*reps)],vals[int(.975*reps)]]

def summarize(rows):
    summary={}
    for method in METHODS:
        es=[r for r in rows if r['method']==method]
        summary[method]={'n':len(es),'accepted':sum(e['accepted'] for e in es),
            'final_test_cost':sum(e['final_test_cost'] for e in es),
            'recursive_delta':sum(e['recursive_delta'] for e in es),
            'lineages_two_strict_links':sum(e['strict_links']>=2 for e in es),
            'lineages_consecutive_links':sum(e['consecutive_links'] for e in es),
            'cost':{k:sum(e['cost'][k] for e in es) for k in es[0]['cost']}}
    es=[r for r in rows if r['method']=='recursive'];mc={}
    for arm in es[0]['metacognition']['arms']:
        records=[e['metacognition']['arms'][arm] for e in es]
        mc[arm]={'correct':sum(r['correct'] for r in records),'total':sum(r['raw_total'] for r in records),
                 'checked':sum(len(r['checked']) for r in records),
                 'raw_correct':sum(r['raw_correct'] for r in records),
                 'mean_brier':sum(r['brier'] for r in records)/len(records) if records[0]['brier'] is not None else None,
                 'mean_type2_auc':sum(r['type2_auc'] for r in records)/len(records) if records[0]['type2_auc'] is not None else None}
    gains=[(e['metacognition']['arms']['own']['correct']-e['metacognition']['arms']['blind']['correct'])/128 for e in es]
    rec=[e['recursive_delta']/(7*32) for e in es]
    return {'search':summary,'metacognition':mc,'recursive_mean_delta_ci':bootstrap_mean(rec),
            'metacognition_gain_ci':bootstrap_mean(gains),'metacognition_mean_gain':sum(gains)/len(gains)}
