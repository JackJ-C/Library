"""Independent evaluator. Hidden mechanism, change level and correctness never reach Queen."""
from random import Random
from collections import Counter
from itertools import product
import copy,json
from .grammar import P,STATES,predict,show
from .queen import Queen,NotLicensed,Budget,METHODS,canonical
from .world import World,Port

def parameters(seed,confirm=False):
    r=Random(seed*7919+331)
    return (r.choice((3,4,5,6) if confirm else (0,1,2)),r.randrange(2),
            r.choice(('less','equals')) if confirm else 'less',
            r.choice((2,3,4,5)) if confirm else 1,r.sample(range(1,7),4))

def challenge(q,w,oldtree=None):
    rows=[];savedlast=q.last
    try:
        for s in STATES:
            if s[0]%2==0:continue
            p,o,obj,h=s;trial=World(w.parameters);trial.level=w.level;trial.bias=w.bias[:];trial.outside=w.outside;trial.positions=[0,0];trial.positions[obj]=p;trial.positions[1-obj]=o;trial.last=h
            q.last=h;goal=(p+1+(p+o+h+obj)%6)%7
            before=trial.sense()
            try:intended=q.decide(before,obj,goal);a=q._emit(intended);after=trial.move(obj,a,'evaluation');ok=trial.positions[obj]==goal
            except NotLicensed:intended=None;a=None;ok=False
            g=trial.gain(s)
            old_gain=predict(oldtree,s) if oldtree is not None else None
            rows.append({'state':list(s),'goal':goal,'command':a,'intended_command':intended,'correct':ok,'gain_gold':g,
                         'old_rule_still_applicable':old_gain==g})
    finally:q.last=savedlast
    return rows

def attribution_cases(q,w,intents,seed):
    r=Random(seed);output=[]
    for (intent,physics,bias,level) in intents[::max(1,len(intents)//8)][:8]:
        own=q.read(intent);obs=next(o for i,o in q.pairs if i==intent);after=q.read(obs)['after']
        for symmetric in (False,True):
            other=World(w.parameters);other.level=level;other.positions=physics['before'][:];other.last=physics['state'][3];other.bias=bias[:]
            alternative=physics['command'] if symmetric else (physics['command']+1)%7
            before=other.sense();alt=other.move(physics['state'][2],alternative,'other_actor')
            paths=[{'before':own['before'],'after':after},{'before':before,'after':alt}]
            truth=0
            if r.randrange(2):paths.reverse();truth=1
            answer=q.attribute(intent,{'paths':paths})
            swapped=q.attribute(intent,{'paths':paths[::-1]})
            output.append({'intent':intent,'packet':{'paths':paths},'truth_gold':truth,'symmetric':symmetric,
                'answer':answer,'permutation_ok':swapped['probabilities']==answer['probabilities'][::-1],
                'alternate_actually_executed':{'command':alternative,'event':other.events[-1]}})
    return output

def trajectory(seed,method='library',confirm=False,verbose=False,auxiliary=False):
    w=World(parameters(seed,confirm));q=Queen(seed,method);port=Port(w)
    counts=Counter();stages=[];intents=[];prefixes=[];diagnoses=[]
    first=q.repair(port)
    if verbose:print('bootstrap',first['status'],q.tree,flush=True)
    for level in range(4):
        w.level=level
        if level==2:w.bias[0]=2
        if level==3:q._emit=lambda a:(-a)%7
        oldtree=q.tree;newbefore=len(q.revisions);repairs=[];live=[]
        states=list(product((0,),range(7),range(2),range(7)))
        Random(seed*397+level+102).shuffle(states)
        # All 98 requests predeclared and target-independent. No hidden event notification.
        for s in states:
            q.prepare(port,s)
            obj=s[2];goal=1+(s[1]+s[3])%6
            row=q.act(port,obj,goal)
            correct=row['executed'] and w.positions[obj]==goal
            counts['online_total']+=1;counts['online_correct']+=correct
            counts['online_blocked']+=not row['executed'];counts['online_wrong']+=row['executed'] and not correct
            if row['executed']:
                gold=copy.deepcopy(w.events[-1]);intents.append((row['intention'],gold,w.bias[:],level))
            live.append({'state_requested':list(s),'goal':goal,'outcome':row,'correct_gold':correct})
            if ((row['executed'] and row['mismatch']) or (not row['executed'] and row['reason']!='no supported action')) and len(repairs)<6:
                revision=q.repair(port);repairs.append(revision)
                if verbose:print('repair',level,revision['status'],revision.get('cost'),show(q.tree),flush=True)
        future=challenge(q,w,oldtree)
        counts['future_total']+=len(future);counts['future_correct']+=sum(x['correct'] for x in future)
        counts['regression_denominator']+=sum(x['old_rule_still_applicable'] for x in future)
        counts['regressions']+=sum(x['old_rule_still_applicable'] and not x['correct'] for x in future)
        reinterpret=q.reinterpret() if q.tree else []
        stages.append({'level_gold':level,'live':live,'repairs':repairs,'model':q.tree,'future':future,
            'reinterpretation':reinterpret,'revision_count':len(q.revisions)-newbefore})
        prefixes.append([len(q.ledger.records),canonical(q.ledger.export())])
        if verbose:print('STAGE',level,sum(x['correct'] for x in future),len(future),flush=True)
    identities=attribution_cases(q,w,intents,seed)
    counts['attribution_distinct_total']=sum(not x['symmetric'] for x in identities)
    counts['attribution_distinct_correct']=sum(not x['symmetric'] and x['answer']['options']==[x['truth_gold']] for x in identities)
    counts['attribution_symmetric_total']=sum(x['symmetric'] for x in identities)
    counts['attribution_symmetric_correct']=sum(x['symmetric'] and x['answer']['probabilities']==[.5,.5] for x in identities)
    counts['attribution_false_certain']=sum(len(x['answer']['options'])==1 and x['truth_gold'] not in x['answer']['options'] for x in identities)
    counts['post_boot_revisions']=sum(r['actual_update'] for r in q.revisions[1:])
    counts['structure_revisions']=sum(r['structural_change'] for r in q.revisions)
    counts['same_instance']=int(id(q)==q.birth and id(q.ledger)==q.book_birth)
    counts['history_unchanged']=int(all(canonical(q.ledger.export()[:n])==data for n,data in prefixes))
    main_revision_count=len(q.revisions);main_end_seq=len(q.ledger.records)
    main_cost=dict(q.cost);main_physics_cost=dict(w.cost)
    recovery=recovery_evidence(q,w,seed) if auxiliary and method in ('library','plain','no_history') and q.valid() else None
    gate=permission_test(q,w) if method in ('library','plain') else None
    return {'seed':seed,'method':method,'parameters_gold':w.parameters,'counts':dict(counts),
            'cost':main_cost,'physics_cost':main_physics_cost,'auxiliary_recovery':recovery,'permission_test':gate,
            'extra_cost':{k:v-main_cost.get(k,0) for k,v in q.cost.items()},'bootstrap':first,'stages':stages,
            'revisions':q.revisions[:main_revision_count],'extra_revisions':q.revisions[main_revision_count:],'main_end_seq':main_end_seq,'component_changes':q.component_changes,'attribution':identities,
            'ledger':q.ledger.export(),'invalid':sorted(q.ledger.invalid),'physics':w.events}

def recovery_evidence(q,w,seed):
    """Same lived object. First erase derived control; then withdraw current raw action evidence.
    Both interventions have identical stable physics. Sequential order and trust assumptions explicit.
    """
    p=Port(w);qid=id(q);bookid=id(q.ledger);before_cal=q.calibration
    before_records=len(q.ledger.records)
    q.tree=None;q.function=q.bound=None
    with_history=q.repair(p)
    future_with=challenge(q,w)
    # Withdraw evidence, not overwrite the events. Keep unrelated calibration and own records.
    removed=[]
    for i,o in list(q.pairs):
        if i>=q.floor and o not in q.ledger.invalid:q.ledger.revoke(o,'paired history-ablation intervention');removed.append(o)
    stopped=not q.valid();calibration_retained=before_cal not in q.ledger.invalid
    q.tree=None;q.function=q.bound=None;q.pending=None
    without_history=q.repair(p)
    future_without=challenge(q,w)
    return {'same_object':id(q)==qid and id(q.ledger)==bookid,'raw_records_not_deleted':len(q.ledger.records)>before_records,
        'with_history':with_history,'without_history':without_history,'with_future':future_with,'without_future':future_without,
        'withdrawal_stops_permission':stopped,'unrelated_calibration_retained':calibration_retained,
        'removed':removed,'interpretation':'stable-physics sequential cache-loss/history-withdrawal comparison, not independently randomized agents'}

def permission_test(q,w):
    if not q.valid():return {'ready':False}
    k=q.revisions[-1]['support'][-1];cal=q.calibration
    q.ledger.revoke(k,'support withdrawal test');count=w.cost['task_moves'];p=Port(w)
    stopped=not q.act(p,0,3)['executed'] and not q.execute(p,0,3)['executed']
    try:q.decide(p.sense(),0,3);direct=False
    except NotLicensed:direct=True
    permit_lost=not q.valid();unchanged=w.cost['task_moves']==count
    repair=q.repair(p)
    return {'ready':True,'support':k,'permission_lost':permit_lost,'entries_blocked':stopped and direct,
        'world_not_changed_by_blocked_tasks':unchanged,'unrelated_calibration_preserved':cal not in q.ledger.invalid,
        'regained':q.valid(),'repair':repair}
