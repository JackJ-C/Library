"""Evaluator code; gold is never passed to Queen. Independent seed = whole lineage."""
import copy
import json
from random import Random
from collections import Counter
from .core import Queen, World, Port, PRIOR, P, score_program, model_probe, propose, learn_in_model

METHODS=('evolve','plain','fixed_query','hand_balance','frozen_proposer')


def truth(world,q):
    # Evaluator-only phenotype. No implementation or name supplied to diagnosis.
    return [q._emit(1),world.bias[0],world.bias[1],world.parameters[-1][0]]


def emitter(k, nonlinear=False):
    def fn(a):return (k*a+int(nonlinear and a==3))%7
    return fn


def interventions(q,world,seed):
    """Matched independent world forks. Belief deletion/swap occurs in the SAME
    planning primitive as decide. No live license is forged for wrong-belief arms.
    This is a controlled downstream assay, not a naturally occurring error rate.
    """
    rng=Random(seed);rows=[];counts=Counter();s=q.self_options[0];g=q.tree[1]
    options={'full':(s,),'removed':tuple(range(1,7)),
             'swapped':(s%6+1,),'restored':(s,),'composite':None}
    for _ in range(28):
        obj=rng.randrange(2);p=rng.randrange(7);other=rng.randrange(7);goal=rng.randrange(7)
        initial=[p,other] if obj==0 else [other,p]
        cells=[]
        for mode,opts in options.items():
            trial=copy.deepcopy(world);trial.place(initial)
            # Matched information strong control stores only s*g, no explicit self label.
            action=((goal-p)*pow(s*g,-1,7))%7 if mode=='composite' else propose(opts,g,p,goal)
            issued=None if action is None else q._emit(action)
            if action is not None:trial.move(obj,issued,'assay')
            good=action is not None and trial.positions[obj]==goal
            counts[mode+'_correct']+=good;counts[mode+'_total']+=1
            counts[mode+'_blocked']+=action is None
            if mode=='full':
                counts['own_prediction_checks']+=1;counts['own_prediction_correct']+=issued==s*action%7
                counts['own_unfitted_input_checks']+=action in (3,4,5,6)
                counts['own_unfitted_input_correct']+=(action in (3,4,5,6) and issued==s*action%7)
            cells.append([mode,action,issued,trial.positions[obj],good])
        rows.append({'position':p,'object':obj,'other':other,'goal':goal,'inferred_self':s,
                     'inferred_world':g,'gold_self':q._emit(1),'gold_world':world.parameters[-1][0],
                     'modes':cells})
    return {'counts':dict(counts),'rows':rows}


def history_tests(q,world,seed):
    rng=Random(seed)
    # Use actual paired records and anonymous before/after Worker packets; no author/id.
    i,o=q.pairs[-1];intent=q.read(i);receipt=q.read(o)
    own={'before':intent['before'],'after':receipt['after']}
    alt=copy.deepcopy(own);alt['after']['workers'][0][0]=(alt['after']['workers'][0][0]+1)%7
    paths=[own,alt];author=rng.randrange(2)
    if author:paths.reverse()
    a=q.attribute(i,{'paths':paths})  # Actual inherited M54 method, not new label matching.
    same=q.attribute(i,{'paths':[own,copy.deepcopy(own)]})
    reverse=q.attribute(i,{'paths':paths[::-1]})
    return {'distinct':a['probabilities'],'truth':author,'symmetric':same['probabilities'],
            'equivariant':reverse['probabilities']==a['probabilities'][::-1],
            'scope':'supplied own receipt and two-candidate trusted custody; not spontaneous identity'}


def episode(seed,method,full_trace=False):
    rng=Random(seed);q=Queen(seed,'plain' if method=='plain' else 'library')
    if method=='hand_balance':q.policy=score_program('balance')
    w=World((0,0,'less',3,[rng.randrange(1,7),2,3,4]));port=Port(w)
    q._emit=emitter(rng.randrange(1,7));w.bias=[rng.randrange(7),rng.randrange(7)]
    original_id=id(q);ledger_id=id(q.ledger);counts=Counter();timeline=[];assays=[];metas=[];origins=[]
    # Three unannounced, independently timed changes, separate from the four-step audit clock.
    kinds=['self','worker','world'];rng.shuffle(kinds)
    events={7+11*j+rng.randrange(3):kind for j,kind in enumerate(kinds)}
    initial=q.diagnose(port);counts['diagnoses']+=1;counts['diagnoses_correct']+=initial.get('identified')==truth(w,q)
    for tick in range(42):
        event=events.get(tick)
        if event=='self':q._emit=emitter(q._emit(1)%6+1)
        elif event=='worker':
            worker=rng.randrange(2);w.bias[worker]=(w.bias[worker]+rng.randrange(1,7))%7
        elif event=='world':
            params=list(w.parameters);params[-1]=[w.parameters[-1][0]%6+1,2,3,4];w.parameters=tuple(params)
        obj=rng.randrange(2);goal=rng.randrange(7)
        old_truth=truth(w,q);step=q.step(port,obj,goal)
        good=step['executed'] and w.positions[obj]==goal
        counts['online_total']+=1;counts['online_correct']+=good
        counts['online_errors']+=step['executed'] and not good;counts['online_blocked']+=not step['executed']
        review=None
        if tick%4==0 or not q.r_valid():
            prev=tuple(q.H[0]) if len(q.H)==1 else None
            c0=q.r_cost.copy();review=q.diagnose(port)
            counts['diagnoses']+=1;counts['diagnoses_correct']+=review.get('identified')==truth(w,q)
            counts['model_changes']+=prev!=tuple(review.get('identified',[]))
            review_cost={k:v-c0[k] for k,v in q.r_cost.items()}
            if tick>=12:
                counts['late_probes']+=review_cost.get('probe_requests',0);counts['late_reviews']+=1
            review={'identified':review.get('identified'),'status':review['status'],'queries':[s['query'] for s in review['steps']],
                    'cost':review_cost,'version':q.version,'gold':truth(w,q)}
            q.retrospective()
        if tick in (10,22,34):
            if method in ('evolve','plain','frozen_proposer'):
                shadow=copy.deepcopy(q)
                parent=q.evolve(seed*991+tick,method=='frozen_proposer')
                counter=shadow.evolve(seed*991+tick,True)
                # New h-values independent of diagnosis; test results never enter q.evolve.
                held=[PRIOR[Random(seed*37+tick*11).randrange(len(PRIOR))]]
                primary_score=learn_in_model(q.policy.ast,held)
                counter_score=learn_in_model(shadow.policy.ast,held)
                metas.append({'tick':tick,'primary':parent,'frozen_parent_counterfactual':counter,
                              'future_learning_score':list(primary_score),'counterfactual_score':list(counter_score)})
        if tick in (12,24,36):
            assays.append(interventions(q,w,seed*127+tick))
            if q.pairs:origins.append(history_tests(q,w,seed*31+tick))
        timeline.append({'tick':tick,'event_gold_only':event,'truth':old_truth,'step':step,'success_gold_only':good,'review':review})
        if id(q)!=original_id or id(q.ledger)!=ledger_id:raise AssertionError('Queen replaced')
    totals=Counter()
    for a in assays:totals.update(a['counts'])
    counts.update(totals)
    counts['meta_accepted']=sum(m['primary']['accepted'] for m in metas)
    counts['recursive_counterfactual_better']=sum(m['future_learning_score']<m['counterfactual_score'] for m in metas[1:])
    counts['origin_distinct_correct']=sum(r['distinct'][r['truth']]==1 for r in origins)
    counts['origin_symmetric_uncertain']=sum(r['symmetric']==[.5,.5] for r in origins)
    counts['origin_cases']=len(origins)
    counts['origin_permutations']=sum(r['equivariant'] for r in origins)
    counts['same_queen']=1
    # Certificates depend on real raw evidence; unrelated self/world claims remain after sensor withdrawal.
    calibration_obs=next(r.seq for r in reversed(q.ledger.records) if r.kind=='R_calibration')
    old_self=q.self_permission;q.ledger.revoke(calibration_obs,'R experiment withdraw observation')
    denied=not q.r_valid();preserved=old_self not in q.ledger.invalid
    counts['withdrawal_gated']=denied;counts['unrelated_self_preserved']=preserved
    recovery=q.diagnose(port);counts['recovery']=recovery['status']=='adopted'
    return {'seed':seed,'method':method,'counts':dict(counts),'actual_cost':dict(q.r_cost),
            'timeline':timeline,'assays':assays,'origins':origins,'meta':metas,
            'strict_RSI_gate':counts['meta_accepted']>=2 and counts['recursive_counterfactual_better']>=2,
            'ledger':q.ledger.export() if full_trace else None}


def stress():
    q=Queen();w=World((0,0,'less',3,[2,2,2,2]));q._emit=emitter(2,True);p=Port(w)
    d=q.diagnose(p);was_licensed=q.r_valid()
    # Force an unseen requested code 3 via a goal consistent with the current self model.
    before=p.sense();decoded=q.decode(before)[0];goal=(decoded[0]+2*2*3)%7
    r=q.step(p,0,goal);valid_after=q.r_valid();review=q.diagnose(p)
    # The archived counterexample is retested, not silently discarded on re-entry.
    # A correct stop is not an open-ended repair or consciousness evidence.
    h=tuple(h for h in PRIOR if h[1:3]==(0,0) and h[0]*h[3]%7==3)
    own_predictions=sorted({v[0] for v in h})
    control_actions={propose((v[0],),v[3],0,1) for v in h}
    return {'nonlinear_self':{'initial_diagnosis':d.get('identified'),'initially_licensed':was_licensed,
                'future':r,'revoked_after_counterexample':not valid_after,
                'relicensed_by_inadequate_recheck':q.r_valid(),'recheck':review.get('identified')},
            'self_uncertain_control_certain':{'compatible_models':[list(v) for v in h],
                'own_multiplier_options':own_predictions,'action_options':sorted(control_actions)},
            'remaining_fixed_components':['diagnostic hypothesis family','query grammar','candidate mutation operator',
                  'candidate features','acceptance rule','M54 interpreter','trusted efference','calibration anchors']}


def batch(seeds):
    episodes=[];total={};cost={}
    for method in METHODS:
        t=Counter();c=Counter()
        for seed in seeds:
            e=episode(seed,method,method=='evolve' and seed==seeds[0]);episodes.append(e)
            t.update(e['counts']);c.update(e['actual_cost'])
        total[method]=dict(t);cost[method]=dict(c)
    return {'seeds':seeds,'summary':total,'cost':cost,'episodes':episodes,'stress':stress()}
