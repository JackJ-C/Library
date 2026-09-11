"""Paired evaluation; unseen full trajectories, fixed probes, explicit causal interventions.
Main actor remains the same M41-derived Queen. Independent physics labels stay here.
"""
from random import Random
from collections import Counter
import json
from .core import Queen, MODELS, METHODS, common_inverse, compile_control, canonical, LINEAR
from .world import World, AnonymousPort


def make(seed,method='library'):
    w=World(seed);q=Queen(method);q.attach(w.port());q.bootstrap_components()
    return q,w,AnonymousPort(w)


def task(q,w,obj,delta,rng,tick):
    w.positions={'apple':rng.randrange(5),'teacup':rng.randrange(5)}
    before=dict(w.positions);goal=(before[obj]+delta)%5
    outcome=q.act(obj,goal,tick,True)
    after=dict(w.positions)
    return {'before':before,'after':after,'object':obj,'goal':goal,'delta':delta,
            'executed':outcome['executed'],'command':outcome['command'],
            'correct':outcome['executed'] and after[obj]==goal,'map':list(w.permutation),
            'intention':outcome.get('intent'),'reason':outcome.get('reason')}


def causal_trials(q,w,seed):
    """Same saved state, position and task. Remove source-compatibility constraints only.
    Weaken the candidate set to the initial prior and compile the resulting conservative policy.
    No wrong author supplied. Not a separate natural population or a new learning episode.
    """
    if not q.valid():return None
    policy=q.selected;before_fn=policy['function'];before_bound=policy['bound']
    before_inverse=policy['inverse'];old_views=q.last_views
    initial_world=dict(w.positions);identity_before=id(q)
    outputs={}
    for arm in ('factual','remove_source_constraints','restore'):
        fn=compile_control(common_inverse(MODELS)) if arm=='remove_source_constraints' else before_fn
        if arm=='remove_source_constraints':
            weak_scope=q.book.append('counterfactual_scope','evaluator',
                {'scene':q.active_scene,'models':[list(m) for m in MODELS],
                 'inverse':list(common_inverse(MODELS)),
                 'intervention':'remove action-source correspondence; retain the full prior'},
                refs=(policy['review'],),deps=(policy['certificate'],))
            weak_cert=q.book.append('control_permission','evaluator',
                {'scope':'conservative counterfactual only'},deps=(weak_scope,))
            weakened=dict(policy,scope=weak_scope,certificate=weak_cert,function=fn,bound=fn,
                          inverse=common_inverse(MODELS),models=MODELS)
            q.policies[q.active_scene]=weakened;q.selected=weakened
        else:q.policies[q.active_scene]=policy;q.selected=policy
        rng=Random(seed)
        outputs[arm]=[task(q,w,o,d,rng,q.phase) for o in ('apple','teacup') for d in range(5)]
        q.last_views=old_views
    q.policies[q.active_scene]=policy;q.selected=policy
    policy['function']=before_fn;policy['bound']=before_bound;policy['inverse']=before_inverse
    w.positions=initial_world
    return {'arms':outputs,'same_instance':id(q)==identity_before,'same_nonintervened_judge':q._judge is policy['judge_binding'],
            'scope':'counterfactual alteration of evidence-routing constraint; same tasks; not naturally adopted corruption'}


def trajectory(seed,method,keep_ledger=True):
    q,w,port=make(seed,method);qid,bid=id(q),id(q.book)
    events=[];counts=Counter();stages=[];snapshots=[];public=[]
    for phase in range(16):
        scene=phase%4;w.set_scene(scene,phase);q.activate(scene,phase)
        rng=Random(seed*1009+phase)
        precheck=None
        if q.valid():
            precheck=task(q,w,('apple','teacup')[phase%2],rng.randrange(1,5),rng,phase)
            q.receive_feedback(precheck['correct'])
            counts['prechecks']+=1;counts['precheck_correct']+=precheck['correct']
        learning=None
        if not q.valid() or method=='fixed_probe':learning=q.learn(port)
        trial_rng=Random(seed*100003+phase*193)
        future=[task(q,w,o,d,trial_rng,phase) for o in ('apple','teacup') for d in range(5)]
        counts['future_tasks']+=len(future);counts['future_correct']+=sum(r['correct'] for r in future)
        counts['future_blocked']+=sum(not r['executed'] for r in future)
        counts['future_wrong']+=sum(r['executed'] and not r['correct'] for r in future)
        causality=causal_trials(q,w,seed*8191+phase) if method in ('library','plain') else None
        if causality:
            for arm, rows in causality['arms'].items():
                counts['causal_'+arm+'_correct']+=sum(r['correct'] for r in rows)
                counts['causal_'+arm+'_total']+=len(rows)
        if learning:
            counts['learning_calls']+=1;counts['complete_reconstructions']+=learning['complete']
            counts['adoptions']+=learning['adopted']
            for key,value in learning['cost'].items():counts['cost_'+key]+=value
            # Current interval attribution scored separately from functional reconstruction.
            latest=[g for g in learning['groups'] if g['interval']==learning['interval']]
            actual=port.private_log[-1]['true_source_index']
            if latest:
                options=latest[-1]['source_options'];counts['ownership_cases']+=1
                counts['ownership_true_included']+=actual in options
                counts['ownership_unique']+=len(options)==1
                counts['ownership_unique_correct']+=(options==[actual])
            else:options=[]
        else:options=None
        policy=q.policies.get(scene)
        representation=policy['representation'] if policy else None
        counts['nonlinear_scene_tasks']+=int(w.permutation not in LINEAR)*len(future)
        counts['nonlinear_scene_correct']+=int(w.permutation not in LINEAR)*sum(r['correct'] for r in future)
        stages.append({'phase':phase,'scene':scene,'map_evaluator_only':list(w.permutation),
            'precheck':precheck,'learning':learning,'source_options':options,
            'true_source_index_evaluator_only':None if learning is None else port.private_log[-1]['true_source_index'],
            'representation':representation,'future':future,'causal':causality,
            'control_revision':q.control_revision,'history_size':len(q.book.ledger.records)})
        # Aggregate future feedback is now observable; it never tunes the already reported tasks.
        q.receive_feedback(all(r['correct'] for r in future))
        if phase in (3,7):
            snapshots.append([len(q.book.ledger.records),canonical(q.book.export())])
        if not (id(q)==qid and id(q.book)==bid):raise AssertionError('replaced lived Queen')
    preserved=all(canonical(q.book.export()[:n])==text for n,text in snapshots)
    counts['same_object']=1;counts['history_preserved']=int(preserved)
    counts['control_revisions']=q.control_revision
    counts['at_least_three_revisions']=int(q.control_revision>=3)
    tests=gate_test(q,w,port.private_log) if method in ('library','plain') else None
    return {'seed':seed,'method':method,'counts':dict(counts),'stages':stages,
            'failures':q.failures,'private_physics':port.private_log,'gate':tests,
            'ledger':q.book.export() if keep_ledger else None}


def gate_test(q,w,log=None):
    # Reuse the same lived object; if last context failed, revalidate within real current scope.
    ports=[]
    if not q.valid():
        p=AnonymousPort(w);q.learn(p);ports.append(p)
    if not q.valid():return {'available':False}
    scope=q.selected['scope'];body=json.loads(q.book.ledger.records[scope].body)['data']
    roots=q.book.ledger.records[scope].deps
    support=next(k for k in roots if q.book.ledger.records[k].kind=='anonymous_effects')
    q.book.revoke(support,'observed source trace withdrawn')
    from library_m37.core import NotLicensed,probe_packet
    blocked=[]
    for method in ('act','execute','decide','predict'):
        before=dict(w.positions)
        try:
            if method in ('act','execute'):result=not getattr(q,method)('apple',2,99)['executed']
            else:getattr(q,method)(probe_packet(0));result=False
        except NotLicensed:result=True
        blocked.append(result and before==w.positions)
    q.invalidate_control('withdrawn observation requires fresh proof')
    p=AnonymousPort(w);q.learn(p);ports.append(p)
    if log is not None:
        for p in ports:log.extend(p.private_log)
    rows=[task(q,w,'apple',d,Random(d+1),99) for d in range(5)]
    return {'available':True,'support':support,'all_entries_blocked':all(blocked),
            'future_restored':all(r['correct'] for r in rows),'same_lived_object':id(q)==q._same_identity}


def pressures(seed=47):
    result={}
    for mode in ('echo_equal','echo_different'):
        q,w,_=make(seed);w.set_scene(1,0)
        if mode=='echo_different':w.other_maps=[m for m in MODELS if m!=w.permutation][:2]
        q.activate(1,0);port=AnonymousPort(w,mode);r=q.learn(port)
        test=[task(q,w,'apple',d,Random(d),0) for d in range(5)]
        result[mode]={'models':r['models'],'source_options':r['groups'][-1]['source_options'],
                      'complete':r['complete'],'cost':r['cost'],'test':test,
                      'permit':q.valid(),'true_source':port.private_log[-1]['true_source_index']}
    # A position-dependent mechanism lies outside the zero-preserving stationary action-map family.
    q,w,_=make(seed);w.set_scene(1,0);q.activate(1,0);q.learn(AnonymousPort(w))
    accepted=q.valid();w.position_switch=True
    w.positions={'apple':4,'teacup':2};r=q.act('apple',0,1)
    correct=r['executed'] and w.positions['apple']==0
    q.receive_feedback(correct)
    result['unseen_state_dependence']={'previously_licensed':accepted,'actual_error':not correct,
        'licence_after_observed_error':q.valid(),'unknown_mechanism_repaired':False}
    return result


def batch(seeds):
    rows=[];totals={m:Counter() for m in METHODS}
    for seed in seeds:
        for method in METHODS:
            row=trajectory(seed,method,method=='library')
            rows.append(row);totals[method].update(row['counts'])
    return {'seeds':list(seeds),'rows':rows,'summary':{m:dict(c) for m,c in totals.items()}}
