"""Readout-only evaluator. Hidden modes, raw counterfactual truth and schedules do not
enter Queen.update_online/current_reliability. All methods share exogenous streams.
"""
import json
from random import Random
from collections import Counter
from .online import make_queen, choose_check
from src.core import Port

METHODS=('adaptive','plain','frozen','global','fixed','compiled')
WARMUP=160
STEPS=512


def task(seed,t):
    r=Random(seed*100003+t*1223+76531)
    return [r.randrange(7),r.randrange(7)],r.randrange(2),r.randrange(7),r.choice((1,3)),r


def stream(seed,method='adaptive',keep_ledger=False,keep_queen=False):
    q,w=make_queen(seed,method)
    qid,lid=id(q),id(q.ledger)
    training=[]
    for t in range(-WARMUP,0):
        positions,obj,goal,repeats,rng=task(seed,t)
        raw,trace,_=q.approximate_plan(q,positions,obj,goal,repeats,rng)
        q.clock=t
        record=q.execute_plan(w,positions,obj,goal,raw,raw,trace,None,False,'train')
        q.training_keys.append(record['label_key'])
        training.append(record['label_key'])
    q.recent_keys=q.training_keys[:]
    q.n_raw=len(training)
    q.rebuild_monitor(training,'initial own raw execution history')
    initial_ref=q.monitor_ref
    initial_model=q.monitor.export()
    schedule_rng=Random(seed^0x67719)
    change_times=(schedule_rng.randrange(144,177),schedule_rng.randrange(320,353))
    rows=[];remaining=0
    for t in range(STEPS):
        if t in change_times:
            q.approximate_plan.donor=not q.approximate_plan.donor  # hidden same-object change
        q.clock=t
        positions,obj,goal,repeats,rng=task(seed,t)
        raw,trace,_=q.approximate_plan(q,positions,obj,goal,repeats,rng)
        forecast=q.current_reliability(trace)
        p=forecast['probability']
        if t%32==0: remaining=8
        checked=choose_check(p,remaining,32-t%32)
        request=raw
        if checked:
            w.place(positions)
            request=q.decide(Port(w).sense(),obj,goal)
            remaining-=1
        # This readout is evaluator-only. It never becomes the label for a checked quick answer.
        raw_gold=(positions[obj]+q.self_options[0]*w.gain((positions[obj],positions[1-obj],obj,w.last))*raw)%7==goal
        r=q.execute_plan(w,positions,obj,goal,raw,request,trace,p,checked,'online')
        q.update_online(r['label_key'],p)
        rows.append({'t':t,'positions':positions,'object':obj,'goal':goal,'raw':raw,
                     'request':request,'trace':trace,'probability':p,'status':forecast['status'],
                     'checked':checked,'raw_correct_evaluator':raw_gold,
                     'observed_correct':r['observed_goal_met'],'intention':r['intention'],
                     'observation':r['observation'],'label':r['label_key'],'remaining':remaining,
                     'model_before':forecast.get('model',forecast.get('history_key'))})
    alarms=q.alarms[:]
    count=Counter()
    count.update(tasks=len(rows),checked=sum(r['checked'] for r in rows),
                 correct=sum(r['observed_correct'] for r in rows),
                 raw_correct=sum(r['raw_correct_evaluator'] for r in rows),
                 unknown=sum(r['status']=='unknown' for r in rows),monitor_updates=q.mon_updates)
    detected=[]
    for t in change_times:
        candidates=[a['time']-t for a in alarms if 0<=a['time']-t<=96]
        detected.append(min(candidates) if candidates else None)
    falses=sum(not any(0<=a['time']-t<=96 for t in change_times) for a in alarms)
    brier=sum(((r['probability'] if r['probability'] is not None else .5)-r['raw_correct_evaluator'])**2 for r in rows)/len(rows)
    late=[r for r in rows if any(48<=r['t']-t<128 for t in change_times)]
    count['late_correct']=sum(r['observed_correct'] for r in late);count['late_tasks']=len(late)
    result={'seed':seed,'method':method,'counts':dict(count),'brier':brier,'alarms':alarms,
            'hidden_change_times':change_times,'detection_delay':detected,'false_alarm_count':falses,
            'initial_monitor':initial_model,'initial_monitor_ref':initial_ref,'rows':rows,
            'scope':'one persistent object; fixture resets positions per task; process changes not signaled',
            'same_queen':id(q)==qid,'same_ledger':id(q.ledger)==lid,
            'physics_evaluator_only':{'emitter':q.self_options[0],'gain':q.tree[1]},
            'training_label_keys':training,'online_cost':dict(q.online_cost),
            'ledger':q.ledger.export() if keep_ledger else None,
            'invalid':sorted(q.ledger.invalid)}
    if keep_queen:return result,q,w
    return result


def resample_interval(values,seed=910315,reps=4000):
    r=Random(seed);n=len(values)
    means=sorted(sum(values[r.randrange(n)] for _ in range(n))/n for _ in range(reps))
    return [means[int(.025*reps)],means[int(.975*reps)]]


def summarize_stream(episodes):
    out={}
    for method in METHODS:
        es=[e for e in episodes if e['method']==method]
        if not es:continue
        c=Counter()
        for e in es:c.update(e['counts'])
        out[method]={'n':len(es),'counts':dict(c),'brier':sum(e['brier'] for e in es)/len(es),
                     'detected_changes':sum(d is not None for e in es for d in e['detection_delay']),
                     'total_changes':2*len(es),'false_alarms':sum(e['false_alarm_count'] for e in es)}
    m={e['seed']:e for e in episodes if e['method']=='adaptive'}
    contrasts={}
    for arm in ('plain','frozen','global','fixed','compiled'):
        es=[e for e in episodes if e['method']==arm]
        gains=[(m[e['seed']]['counts']['correct']-e['counts']['correct'])/STEPS for e in es]
        bs=[e['brier']-m[e['seed']]['brier'] for e in es]
        if gains:contrasts[arm]={'gain':sum(gains)/len(gains),'gain_ci':resample_interval(gains),
                                 'brier_improvement':sum(bs)/len(bs),'brier_ci':resample_interval(bs)}
    return {'methods':out,'paired':contrasts}
