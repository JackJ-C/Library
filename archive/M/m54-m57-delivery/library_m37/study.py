"""评估层：事件时间/类型、真实作者、独立任务正确值不进入 Queen.review。"""
from collections import Counter
from fractions import Fraction as F
from random import Random
from dataclasses import asdict
import json
from library_m12.core import PROGRAMS,simulate,frame_load,compile_judge,reference
from .core import Queen,Budget,NotLicensed,probe_packet,digest,canonical
from .world import World
from .identity import revisit,build_case,project,posterior

METHODS=Queen.METHODS
TICKS=32
EVENT_KINDS=('healthy','self','worker','environment','combined','self')


def scheme(seed):
    rng=Random(seed)
    kinds=list(EVENT_KINDS);rng.shuffle(kinds)
    times=[rng.randrange(a,a+3) for a in (2,7,12,17,22,27)]
    events=dict(zip(times,kinds))
    tasks=[(rng.choice(('apple','teacup')),rng.randrange(5)) for _ in range(TICKS*3)]
    return events,tasks


def actual_q(q):
    # 只供评分：独立运行而不读取函数ID。绝不回传此结果。
    packet=probe_packet(-1)
    d=q._judge(packet)
    return [p for p in PROGRAMS if simulate(p,packet)==d]


def expected_patch(q,world):
    expected=[]
    if actual_q(q)!=[(0,0,0)]:expected.append('queen_judge')
    for i,w in enumerate(world.workers):
        if w.emit(F(0))!=0:expected.append(f'worker{i}')
    if q.dynamics!=world.gain:expected.append('environment_model')
    return expected


def judgment_projection(judge,gain,decoders,positions,bias,obj,target,previous):
    # 同一物理初态、同一请求；只有被比较的函数/解码器/世界模型不同。
    from .core import packet_from_views
    if gain is None:return False
    a,b=decoders[0]
    view={o:[str(a*F(p+v+bias[0])+b) for v in (-1,0,1)] for o,p in positions.items() if o!='_gain'}
    packet=packet_from_views(view,previous,obj,77777)
    d=judge(packet)
    if d.value.denominator!=1:return False
    command=((target-int(d.value))*gain)%5
    return (positions[obj]+positions['_gain']*command)%5==target


def one_episode(seed,method,keep_trace=False):
    world=World(seed%5,(seed+2)%5);q=Queen(method);q.attach(world.port())
    events,tasks=scheme(seed);rng=Random(seed^0x419D)
    rows=[];ids=[];counts=Counter();costs=Counter();witnesses=[];old_prefixes=[]
    pending_events=[];hidden=[];cycles=[];paired=[]
    for tick in range(TICKS):
        q.book.clock=tick;world.tick=tick
        if tick in events:
            hidden.append({'tick':tick,**world.change(events[tick],q,Random((seed*104729)^tick^0x29AF))})
            pending_events.append(tick)
        expected=expected_patch(q,world)
        obj,target=tasks[tick*3]
        live_before=dict(world.positions)
        out=q.act(obj,target,tick)
        live_execution={'before':live_before,'after':dict(world.positions),'gain':world.gain,**out}
        correct=bool(out['executed'] and world.positions[obj]==target)
        counts['live_tasks']+=1;counts['live_correct']+=correct
        # 固定审查周期，不通知事件，异常也会主动唤起审查。
        saved_positions=dict(world.positions,_gain=world.gain)
        saved=(q._judge,q.dynamics,q._port.decoders(),q.last_views)
        old_success=[judgment_projection(saved[0],saved[1],saved[2],saved_positions,
                     world.physical_bias,o,t,saved[3]) for o,t in tasks[tick*3+1:tick*3+3]]
        audit=q.review(tick)
        if audit:
            counts['reviews']+=1
            for k in ('reads','probes','comparisons','bytes_read'):costs[k]+=audit['budget'][k]
            if audit['status']=='accepted':
                counts['resolved']+=1
                if set(audit['patches'])!=set(expected):counts['wrong_patch_sets']+=1
                if audit['patches']:counts['substantive_revisions']+=1
                if audit['patches']:cycles.append(tick)
                counts['unrelated_modifications']+=len(set(audit['patches'])-set(expected))
                new_success=[judgment_projection(q._judge,q.dynamics,q._port.decoders(),saved_positions,
                             world.physical_bias,o,t,saved[3]) for o,t in tasks[tick*3+1:tick*3+3]]
                counts['regressions']+=sum(a and not b for a,b in zip(old_success,new_success))
                counts['control_checks']+=2
                counts['control_correct']+=sum(q.control_model.get(o)==world.gain for o in ('apple','teacup'))
            for et in list(pending_events):
                if audit['status']=='accepted':
                    counts['events_resolved']+=1;counts['event_delay']+=tick-et;pending_events.remove(et)
        # 两项新请求没有进入本次诊断或候选验证；实际同一个 Queen 执行。
        future=[];future_execution=[]
        for j in (1,2):
            o,t=tasks[tick*3+j]
            prior_positions=dict(world.positions)
            ans=q.act(o,t,tick,True)
            future_execution.append({'before':prior_positions,'after':dict(world.positions),'gain':world.gain,**ans})
            good=bool(ans['executed'] and world.positions[o]==t)
            future.append(good)
            counts['future_tasks']+=1;counts['future_correct']+=good
            if audit and audit['status']=='accepted':
                counts['post_review_tasks']+=1;counts['post_review_correct']+=good
            if ans['executed']:
                move=dict(world.moves[-1])
                w={'commands':[move['command']],
                   'deltas':[(move['after'][o]-move['before'][o])%5],
                   'endpoint':[move['after']['apple'],move['after']['teacup']]}
                wr=q.book.append('intention_memory','queen',w,(ans['action_ref'],))
                witnesses.append((tick,wr,move,q.revision,ans['action_ref']))
        # 跨过若干次任务和修订后，才重访旧意图；候选顺序和别名独立重排。
        if tick in (8,16,24,31) and witnesses:
            eligible=[r for r in witnesses if r[0] <= tick-3]
            if eligible:
                wt,wr,m,version,action_ref=eligible[rng.randrange(len(eligible))]
                for kind in ('distinct','anonymous','changed','identical','merge'):
                    selected=(wt,wr,m,version,action_ref)
                    current_action=None
                    if kind=='changed':
                        for candidate in eligible:
                            oldrow=json.loads(q.book.ledger.records[candidate[4]].body)['data']
                            frame=frame_load(oldrow['frame'])
                            current_decision=q._judge(frame.packet)
                            if q.dynamics is not None and current_decision.value.denominator==1:
                                now=((oldrow['target']-int(current_decision.value))*q.dynamics)%5
                                if now!=candidate[2]['command']:
                                    selected=candidate;current_action=now;break
                        if current_action is None:
                            counts['changed_case_not_yet_available']+=1;continue
                    st,sr,sm,sv,_=selected
                    built=build_case(q,sm,sr,kind,rng,current_action)
                    if built is None:continue
                    candidates,truth,other_execution=built
                    res=revisit(q,sr,candidates)
                    ambiguous=kind in ('identical','merge')
                    p=res['probabilities'][truth]
                    counts['identity_cases']+=1
                    counts['identity_ambiguous' if ambiguous else 'identity_identifiable']+=1
                    if ambiguous:
                        ok=res['probabilities']==[.5,.5]
                        counts['ambiguity_calibrated']+=ok
                        counts['false_certainty']+=res['status']=='identified'
                    else:
                        ok=res['status']=='identified' and p==1
                        counts['identity_correct']+=ok
                    # 交换作者/ID/边并重排：只允许输出概率相应置换。
                    swapped=list(reversed(candidates))
                    clean=[project(c) for c in swapped]
                    wit=q.read(sr,Budget()) if res['witness_used'] else None
                    alt=posterior(wit,clean) if wit is not None else {'probabilities':[.5,.5]}
                    equiv=alt['probabilities']==list(reversed(res['probabilities']))
                    counts['identity_equivariance_checks']+=1;counts['identity_equivariance_pass']+=equiv
                    ids.append({'tick':tick,'past_tick':st,'kind':kind,'true_self_index':truth,
                                'old_revision':sv,'other_execution':other_execution,'current_revision':q.revision,
                                'result':res,'correct_as_scoped':ok,'equivariant':equiv,
                                'binary_brier':(res['probabilities'][0]-(truth==0))**2})
        if tick in (8,16,24):
            old_prefixes.append([len(q.book.ledger.records),digest(q.book.export())])
        rows.append({'tick':tick,'before_expected_patch':expected,'live':live_execution,'live_correct':correct,
                     'audit':audit,'future':future,'future_execution':future_execution,'history_size':len(q.book.ledger.records),
                     'revision':q.revision})
    main_physical_cost=dict(world.cost)
    repair_pressure=None
    if method in ('library','plain'):
        from .pressure import exercise_rollback
        repair_pressure=exercise_rollback(q,world)
    preservation=all(digest(q.book.export()[:n])==h for n,h in old_prefixes)
    counts['history_preserved']=preservation
    counts['same_queen']=id(q)==q._initial_id
    counts['cycles_at_least_three']=len(cycles)>=3
    counts['events']=len(events)
    counts['unresolved_events']=len(pending_events)
    counts['reference_dependency_consistent']=q.book.ledger.recompute()==q.book.ledger.invalid
    return {'seed':seed,'method':method,'counts':dict(counts),'budget_cost':dict(costs),
            'physical_cost':main_physical_cost,'post_episode_pressure':repair_pressure,
            'pressure_extra_cost':{k:world.cost[k]-v for k,v in main_physical_cost.items()},'rows':rows,'identity':ids,'events_evaluator_only':hidden,
            'substantive_cycles':cycles,'state_persisted':{'revisions':q.revision,
                'history_records':len(q.book.ledger.records),'pending_explanations':q.unresolved,
                'identity_beliefs':len(q.identity_beliefs)},
            'slices':q.book.export() if keep_trace else None}


def run_batch(seeds,methods=METHODS,trace_first=True):
    rows=[];totals={};budgets={};physical={}
    for method in methods:
        total=Counter();bc=Counter();pc=Counter()
        for seed in seeds:
            row=one_episode(seed,method,trace_first and method=='library')
            rows.append(row);total.update(row['counts']);bc.update(row['budget_cost']);pc.update(row['physical_cost'])
        totals[method]=dict(total);budgets[method]=dict(bc);physical[method]=dict(pc)
    return {'seeds':list(seeds),'summary':totals,'budget_cost':budgets,'physical_cost':physical,'episodes':rows}


if __name__=='__main__':
    r=run_batch(list(range(4)))
    print(json.dumps(r['summary'],indent=2))
