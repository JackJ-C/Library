"""Continuous Queen, paired parent ablations and evaluator-only transfer scores."""
from collections import Counter
from dataclasses import asdict
import json
from .integrity import make_queen, canonical, digest
from .racing import (Program,INITIAL,UNIFORM,candidates,Engine,select_successor,
                     validation,accept,text,race)
from r4_r7 import search
from r4_r7.study import own_diagnosis,p_json
from src.core import Port

ROUNDS=8
HAND=('/', 'info','price')


def concise_nested(rows):
    return [{**{k:v for k,v in r.items() if k!='inner'},'inner':{
        k:v for k,v in r['inner'].items() if k!='trace'},
        'samples':[[s['arm'],s['sample'],s['loss']] for s in r['inner']['trace']]} for r in rows]


def one_choice(parent,pool,engine,scale,q=None,proposer=None):
    chosen,forecast,nested=select_successor(parent if proposer is None else proposer,pool,engine,scale)
    # Commit the forecast BEFORE any adoption check below.
    prediction={'candidate':pool[chosen],'mean':forecast['mean'],'uncert':forecast['uncert'],
                'scale':scale,'parent':parent,'chosen':chosen}
    key=q.add('R22_forecast',prediction,refs=(() if q.meta_ref is None else (q.meta_ref,))) if q else None
    old=validation(parent,engine,scale);new=validation(pool[chosen],engine,scale)
    approved=chosen!=0 and accept(new,old)
    answer=pool[chosen] if approved else parent
    check_key=None
    if q:
        validation_key=q.add('R22_validation_execution',{'task_pool':engine.task_pool,
             'candidate':pool[chosen],'parent':parent,'scale':scale,'losses':new,'parent_losses':old},
             deps=tuple(q.current_history))
        check_key=q.add('R22_checked_forecast',{'forecast':key,'validation_losses':new,
             'validation':validation_key,
             'parent_losses':old,'accepted':approved},deps=(key,validation_key))
        q.calibration_keys.append(check_key)
    return answer,{'parent':parent,'proposer':parent if proposer is None else proposer,'scale':scale,'pool':pool,'outer':forecast,
                   'nested':concise_nested(nested),'prediction_key':key,'check_key':check_key,
                   'new_check':new,'old_check':old,'accepted':approved,'after':answer}


def transfer(ast,task_pool,cases,scale):
    e=Engine(task_pool,cases)
    vals=[e.inner(ast,j,scale)[0] for j in range(6)]
    return sum(vals)/len(vals),vals,dict(e.cost)


def support_stress(q,w):
    root=q.calibration_keys[-1]
    body=q.ledger.records[root].body
    prior=(q.calibration,q.self_permission,q.scope)
    q.ledger.revoke(root,'R23 withdraw actual evaluator prediction/check pair')
    stopped=False
    try:q.require_allocator()
    except PermissionError:stopped=True
    historical=q.add('R23_revisit',{'this_prediction_was_made':True},refs=(root,))
    before=q.allocator.ast
    q.refresh_meta();q.bind_allocator(before)
    return {'withdrawn_stops_improvement':stopped,'old_body_unchanged':body==q.ledger.records[root].body,
            'physical_premises_preserved':all(k not in q.ledger.invalid for k in prior),
            'historical_reference_survives':historical not in q.ledger.invalid,
            'remaining_evidence_rebuilds':q.current_meta()>0}


def episode(seed,method='recursive'):
    q,w=make_queen(seed,'plain' if method=='plain' else 'adaptive')
    qid,lid=id(q),id(q.ledger)
    q.bind_allocator(INITIAL);q.bind_task(0)
    history=[];history_keys=[];rounds=[];actual=search.Cost();spatial=[]
    # The evaluator stores these only; no selection routine sees cases before its output is fixed.
    cases=[search.make_problem(seed*100000+90000+j,n=(24,40,48)[j%3],nq=(18,30)[j%2]) for j in range(24)]
    for g in range(ROUNDS):
        q.meta_generation=g;q.require_allocator();live=[]
        for j in range(8):
            p,target=search.make_problem(seed*100000+g*100+j)
            h,record=q.execute_diagnosis(p,search.Body(p,target),actual)
            roots=tuple(k for pair in record['receipts'] for k in pair)
            fact=q.add('R21_observed_mechanism',{'inferred':h,'problem':p_json(p)},deps=roots)
            history.append((p,h));history_keys.append(fact)
            live.append({'problem':p_json(p),'evaluator_target':target,'observed':record,'fact':fact})
        history=history[-32:];history_keys=history_keys[-32:]
        q.current_history=tuple(history_keys)
        q.refresh_meta();parent=q.allocator.ast;q.bind_allocator(parent,history_keys)
        scale=q.current_meta();parent_bound=q.require_allocator()
        task_pool=[q.search_program.ast]+search.pool(q.search_program.ast,seed*991+g,9)
        pool=candidates(parent,seed*171+g,8)
        engine=Engine(task_pool,history)
        child,main=one_choice(parent,pool,engine,scale,q)
        # Same candidate set, observations and logical quotas; not a separate autonomous history.
        fe=Engine(task_pool,history);ne=Engine(task_pool,history)
        frozen,fc=one_choice(parent,pool,fe,scale,proposer=INITIAL)
        neutral,nc=one_choice(parent,pool,ne,1.)
        q.refresh_meta();q.bind_allocator(child,(main['check_key'],*history_keys))
        actual_rebind=text(child)!=text(parent)
        # The resulting allocator REALLY chooses the task solver used on the next generation.
        q.require_allocator();task_engine=Engine(task_pool,history)
        fit_indices=list(range(0,len(history),2))
        chosen,tr=race(q.allocator,task_pool,lambda a,j:task_engine.loss(a,fit_indices[j%len(fit_indices)]),
                       scale=q.current_meta(),costs=task_engine.cost)
        test_indices=list(range(1,len(history),2))
        newloss=sum(task_engine.loss(chosen,j) for j in test_indices)
        oldloss=sum(task_engine.loss(0,j) for j in test_indices)
        oldtask=q.search_program.ast
        changed_task=newloss<oldloss-1e-12
        if changed_task:q.bind_task(task_pool[chosen])
        q.add('R21_actual_program_adoption',{'allocator':child,'task_before':oldtask,
              'task_after':q.search_program.ast,'allocator_changed':actual_rebind,
              'check_old':oldloss,'check_new':newloss},deps=(q.allocator_ref,))
        # Selection is over. This section is evaluation only and does not update q.
        evaluations={}
        for name,a,s in [('parent',parent,scale),('child',child,scale),('frozen_child',frozen,scale),
                          ('uncalibrated_child',neutral,scale),('initial',INITIAL,scale),('uniform',UNIFORM,scale)]:
            val,parts,cost=transfer(a,task_pool,cases,s)
            evaluations[name]={'mean':val,'parts':parts,'cost':cost}
        pc,cc,bc=(evaluations[n]['mean'] for n in ('parent','child','frozen_child'))
        strict=g>0 and actual_rebind and cc<pc-1e-12 and cc<bc-1e-12
        out=q.step(Port(w),g%2,(w.positions[g%2]+1)%7)
        spatial.append({'generation':g,'step':out})
        rounds.append({'generation':g,'live':live,'history_facts':history_keys[:],
              'task_pool':task_pool,'primary':main,'frozen_counter':fc,'neutral_counter':nc,
              'allocator_rebound':actual_rebind,'task_rebound':changed_task,'task_race':tr,
              'task_check':{'old':oldloss,'new':newloss,'adopted':q.search_program.ast},
              'evaluation_only':evaluations,'strict_link':strict,'regression':cc>pc+1e-12,
              'primary_cost':dict(engine.cost),'counter_cost':dict(fe.cost),'neutral_cost':dict(ne.cost),
              'task_cost':dict(task_engine.cost),'scale_after':q.meta_scale})
        if id(q)!=qid or id(q.ledger)!=lid:raise RuntimeError('persistent object replaced')
    flags=[r['strict_link'] for r in rounds]
    pressure=support_stress(q,w)
    return {'seed':seed,'method':method,'same_queen':True,'same_ledger':True,'rounds':rounds,
        'physical_steps':spatial,'actual_diagnosis_cost':asdict(actual),'pressure':pressure,
        'heldout_evaluator_only':[{'problem':p_json(p),'target':h} for p,h in cases],
        'updates':sum(r['allocator_rebound'] for r in rounds),
        'strict_links':sum(flags),'consecutive':any(a and b for a,b in zip(flags,flags[1:])),
        'regressions':sum(r['regression'] for r in rounds),
        'gain':sum(r['evaluation_only']['frozen_child']['mean']-r['evaluation_only']['child']['mean'] for r in rounds[1:])/7,
        'calibration_gain':sum(r['evaluation_only']['uncalibrated_child']['mean']-r['evaluation_only']['child']['mean'] for r in rounds)/8,
        'ledger':q.ledger.export(),'invalid':sorted(q.ledger.invalid)}
