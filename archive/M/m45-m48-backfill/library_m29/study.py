"""New execution data, ablations and explicit origin coverage.
Baseline task definitions are reused, not claimed to be new hidden tasks.
"""
from random import Random
from unittest.mock import patch
from . import learning as L
from .runtime import canonical,digest,run_find,run_flatmap,FuelExhausted,SemanticError
from .proof import prove
from .bridge import run_bridge,GatedQueen
from library_m25 import experiments as old


def require(ok,msg):
    if not ok:raise AssertionError(msg)


def origins():
    # Actual causal inputs, not a declaration that direct generation erases its roots.
    graph={
      'grammar':{'origin':'supplied_high_level','parents':[]},
      'property_oracle':{'origin':'supplied_high_level','parents':[]},
      'counterexample_coordinator':{'origin':'supplied_high_level','parents':[]},
      'seed_enumerator':{'origin':'supplied_high_level','parents':[]},
      'vm':{'origin':'supplied_semantics','parents':[]},
      'generated_find':{'origin':'generated','parents':['seed_enumerator','grammar','property_oracle','counterexample_coordinator','vm']},
      'generated_flatmap':{'origin':'generated','parents':['seed_enumerator','grammar','property_oracle','counterexample_coordinator','vm']},
      'next_find':{'origin':'generated','parents':['generated_find','generated_flatmap','grammar','property_oracle','counterexample_coordinator','vm']},
      'next_flatmap':{'origin':'generated','parents':['generated_find','generated_flatmap','grammar','property_oracle','counterexample_coordinator','vm']},
      'builder0':{'origin':'generated','parents':['next_find','next_flatmap','grammar','property_oracle','counterexample_coordinator','vm']},
      'builder1':{'origin':'generated','parents':['builder0','next_find','next_flatmap','grammar','property_oracle','counterexample_coordinator','vm']},
      'feedback_law':{'origin':'generated','parents':['next_find','next_flatmap','grammar','property_oracle','counterexample_coordinator','vm']}}
    pending=list(graph);seen=set()
    while pending:
        k=pending.pop()
        if k in seen:continue
        seen.add(k);pending.extend(graph[k]['parents'])
    fixed=[k for k in sorted(seen) if graph[k]['origin']=='supplied_high_level']
    return {'graph':graph,'fixed_high_level_dependencies':fixed,
            'all_high_level_rules_autonomously_originated':not fixed}


def negatives(programs):
    f,p=programs['find']['program'],programs['flatmap']['program']
    e=L.GeneratedEngine(f,p)
    shuffled=[]
    for seed in range(64):
        xs=list(range(97));Random(seed).shuffle(xs)
        found=e.first(xs,lambda x:x%13==0)
        expected=next(x for x in xs if x%13==0)
        shuffled.append({'seed':seed,'actual':found,'expected':expected,'passed':found==expected})
    damaged=[]
    for slot,bad in [('finder',('none',)),('expander',('nil',))]:
        d=L.GeneratedEngine(f,p);setattr(d,slot,bad)
        rejected=False
        try:d.first([1],lambda x:True) if slot=='finder' else d.expand([1],lambda x:(x,))
        except SemanticError:rejected=True
        damaged.append({'slot':slot,'valid_after_change':d.valid(),'rejected':rejected})
    budget=False
    try:run_find(f,range(9),lambda x:x==8,limit=2)
    except FuelExhausted:budget=True
    # This is outside the trusted semantics, not something the proof notices.
    def wrong_vm(program,xs,fn,limit):
        out,m=run_flatmap(program,xs,fn,limit)
        return tuple(reversed(out)),m
    with patch.object(L,'run_flatmap',wrong_vm):
        wrong_primitive=L.GeneratedEngine(f,p).expand([1,2],lambda x:(x,x+10))
    wrong_reference=e.first(range(5),lambda x:True)
    from library_m25.language import make_builder,make_search
    # Previously generated bridge functions, recovered from this run, are used below by caller.
    return {'shuffled':shuffled,'changed_bindings':damaged,'resource_failure':budget,
            'wrong_vm_certificate_still_passes':prove(p,'flatmap')['passed'],
            'wrong_vm_output':wrong_primitive,'wrong_vm_expected':(1,11,2,12),
            'wrong_predicate_selected':wrong_reference,'true_required_candidate':4,
            'raw_uncertified_none_can_miss':run_find(('none',),[1],lambda x:True)[0] is None}


def run():
    # A fresh baseline execution, in memory, does not overwrite old archives.
    L.SEED_ENABLED=True
    baseline_builders,bb=old.learn_builders();baseline_search,bs=old.learn_search()
    baseline_rows,baseline_summary=old.transfer(bb,bs)
    boot=L.bootstrap();require(all(r['status']=='fit' for r in boot.values()),'bootstrap')
    challenges={k:L.challenge(r['program'],k) for k,r in boot.items()}
    require(all(r['failure'] is None for rows in challenges.values() for r in rows),'new length challenge')
    L.SEED_ENABLED=False
    seed_blocked=[]
    for name,call in [('discover',lambda:L.discover('find')),('expand',lambda:next(L.seed_candidates('find')))]:
        try:call();seed_blocked.append(False)
        except RuntimeError:seed_blocked.append(True)
    generations=[];current=boot
    try:
        for number in range(1,4):
            engine=L.GeneratedEngine(current['find']['program'],current['flatmap']['program'])
            generated={k:L.discover(k,engine) for k in ('find','flatmap')}
            require(all(r['status']=='fit' for r in generated.values()),'handoff')
            generations.append({'generation':number,'parents':{k:r['program_sha256'] for k,r in current.items()},
                                'discoveries':generated,'metrics':dict(engine.metrics),
                                'same_programs':all(generated[k]['program']==current[k]['program'] for k in current)})
            current=generated
        engine=L.GeneratedEngine(current['find']['program'],current['flatmap']['program'])
        bridge=run_bridge(engine)
        require(bridge['transfer_summary']==baseline_summary,'different baseline outcomes')
        baseline_equal=(baseline_rows==bridge['transfer_rows'] and
                        [r['expression'] for r in baseline_builders]==[r['expression'] for r in bridge['builders']] and
                        baseline_search['expression']==bridge['search']['expression'])
        require(baseline_equal,'same information control')
        neg=negatives(current)
        # Reuse learned functions, but probe a new hidden branch without feeding it back.
        from library_m25.language import make_builder,make_search
        b0=make_builder(bridge['builders'][0]['expression'])
        b1=make_builder(bridge['builders'][1]['expression'],b0)
        law=make_search(bridge['search']['expression'])
        raw,target,_=old.task(1000,0)
        q=old.Queen(b1,law);latent=lambda x:target(x)+int(x==13)
        fit=q.fit(raw,latent,task_id='M31-latent')
        neg['latent_accepted']=fit['accepted']
        neg['latent_errors']=[x for x in range(-16,17) if q.decide(x)!=latent(x)]
        neg['certificate_valid_before_rebind']=q.valid()
        q.search=lambda *args:0
        neg['certificate_valid_after_rebind']=q.valid()
        # Audit distinction: reporting invalidity is not automatically an execution guard.
        neg['old_queen_still_executes_after_invalidity']=q.decide(2)==target(2)
        guarded=GatedQueen(b1,law)
        guarded.fit(raw,target,task_id='M31-guarded')
        neg['new_guard_executes_while_valid']=guarded.decide(2)==target(2)
        guarded.search=lambda *args:0
        try:
            guarded.decide(2)
            neg['new_guard_denies_obsolete_execution']=False
        except RuntimeError:
            neg['new_guard_denies_obsolete_execution']=True
        coverage=origins()
        return {'bootstrap':boot,'challenges':challenges,'seed_calls_blocked':seed_blocked,
                'generations':generations,'bridge':bridge,'baseline':{'freshly_executed':True,
                'builders':baseline_builders,'search':baseline_search,'summary':baseline_summary,
                'rows_sha256':digest(baseline_rows),'equal_all_rows':baseline_equal},
                'negative_results':neg,'origin_coverage':coverage}
    finally:L.SEED_ENABLED=True
