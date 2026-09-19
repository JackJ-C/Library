"""R34-R36 offline integration in the real inherited Queen. No network/subprocesses.
The experimenter supplies fixture schedules; hidden parameters never enter the learner.
"""
import argparse,hashlib,json,lzma,time
from pathlib import Path
from random import Random
from statistics import mean
from dataclasses import asdict
from collections import Counter
from itertools import permutations
from r28_r31 import study as old
from r28_r31.space import CausalSpace,canonical
from r32_r37.space import MeasuredSpace,Atlas,finite_best
from r32_r37.closure import learn_closure,STATES,ACTIONS

METHODS=('legacy','measured','raw','frozen','certified','plain')
SEEDS={'A':list(range(73100,73116)),'B':list(range(74100,74116))}
GENERATIONS=6


def diff(after,before):return {k:after.get(k,0)-before.get(k,0) for k in sorted(set(after)|set(before))}

def fixture(seed,plain=False):
    q,w=old.make_queen(seed,plain)
    # Experimental intervention into the fixture only, not a diagnostic label given to Queen.
    rng=Random(seed^93471)
    w.parameters=(rng.randrange(7),rng.randrange(2),rng.choice(('less','equals')),rng.randrange(1,6),tuple(rng.sample(range(1,7),4)))
    w.level=3
    # Retire the inherited constant-gain task license; do not leave it advertised as valid.
    q.ledger.revoke(q.permission,'retire old constant-model task entry for new declared closure study')
    port=old.Port(w)
    return q,w,port


def sequence_check(controller,parameters,bias):
    """Evaluator-only new worlds, all 2-action words from all 343 initial states.
    The learned quotient is frozen; these results never reach candidate selection.
    Actions are actually executed via Port; the digest binds the full ordered effect stream.
    """
    w=old.World(parameters);w.level=3;w.bias=list(bias);p=old.Port(w)
    digest=hashlib.sha256();failed=[];checks=0
    for s in STATES:
        for a in ACTIONS:
            for b in ACTIONS:
                p.move(0,s[2],'evaluation_primer');p.place(list(s[:2]))
                before=list(s[:2]);c=controller.groups[s];observed=[];expected=[]
                for action in (a,b):
                    output,c=controller.quotient[c,action];expected.append(list(output))
                    packet=p.move(action[0],action[1],'evaluation_word')
                    after=[(v-bias[j])%7 for j,row in enumerate(packet['workers']) for v in row]
                    if after[:2]!=after[2:]:raise RuntimeError('evaluator calibration mismatch')
                    actual=[(after[j]-before[j])%7 for j in range(2)];before=after[:2]
                    observed.append(actual);checks+=1
                row=[list(s),list(a),list(b),observed]
                digest.update((canonical(row)+'\n').encode())
                if observed!=expected and len(failed)<20:failed.append({'state':s,'actions':[a,b],'expected':expected,'observed':observed})
                # Evaluator scratch event buffers are not learning histories or archived records.
                w.events.clear()
    return {'scope':'all length-two words after full one-step coverage; not unseen state transitions',
            'words':len(STATES)*len(ACTIONS)**2,'transitions':checks,'passed':not failed,
            'failures':failed,'actual_effect_stream_sha256':digest.hexdigest(),'actual_fixture_cost':dict(w.cost)}


def select(parent,proposer,pool,space,engine,method,geometry=None):
    if method=='certified':return finite_best(pool,engine,range(len(engine.blocks)),proposer)
    return old.choose_proposal(parent,proposer,pool,space,engine,geometry or ('raw' if method=='raw' else 'space'))


def episode(seed,method,validate_words=False):
    if method not in METHODS:raise ValueError('method')
    q,w,port=fixture(seed,method=='plain');identity=(id(q),id(q.ledger))
    before=dict(w.cost);controller,cells=learn_closure(q,port);closure_cost=diff(w.cost,before)
    closed=controller.export();atlas=Atlas(q)
    for j in range(3):
        block,ref=q.acquire(old.opaque_problems(seed*100000+j));q.remember(block,ref)
    rounds=[];previous_adoption=False
    for gen in range(GENERATIONS):
        parent=q.require_allocator();previous=q.previous_allocator;oldtask=q.search_program.ast
        block,ref=q.acquire(old.opaque_problems(seed*100000+100+gen));q.remember(block,ref)
        tasks=old.task_pool(oldtask,seed*71+gen);pool=old.candidate_pool(parent,seed*131+gen)
        engine=old.InterventionEngine(tasks,q.history);npilots=min(old.PILOTS,len(q.history)-1)
        columns=[[engine.run(b,j) for b in pool] for j in range(npilots)]
        context={'task_programs':tasks,'inner_budget':old.INNER_BUDGET,'train_cases':old.TRAIN_CASES,
                 'check_cases':old.TEST_CASES,'loss':'diagnostic_query_price/(9*number_of_query_masks)',
                 'simulation':'deterministic inferred mechanisms; independent block identities; reset per query program'}
        if method=='legacy':space=CausalSpace(q,pool,columns,q.block_refs[:npilots])
        else:
            space=MeasuredSpace(q,pool,columns,q.block_refs[:npilots],context)
            atlas.append(space)
        overlap=atlas.overlap(len(atlas.charts)-2,len(atlas.charts)-1) if len(atlas.charts)>1 else None
        proposer=old.INITIAL if method=='frozen' else parent
        candidate,selection=select(parent,proposer,pool,space,engine,method)
        primary_cost=dict(engine.cost)
        branches={'primary':(candidate,selection)}
        for shadow in ('graph','raw','collapsed','shuffled','previous','initial'):
            sp=previous if shadow=='previous' else old.INITIAL if shadow=='initial' else proposer
            gm='space' if shadow in ('previous','initial') else shadow
            if method=='certified' and shadow in ('graph','previous','initial'):
                branches[shadow]=finite_best(pool,engine,range(len(engine.blocks)),sp)
            else:branches[shadow]=old.choose_proposal(parent,sp,pool,space,engine,gm)
        invariance=[]
        for perm in permutations(range(npilots)):
            cls=CausalSpace if method=='legacy' else MeasuredSpace
            args=(q,pool,[columns[j] for j in perm],[q.block_refs[j] for j in perm])
            pspace=cls(*args) if method=='legacy' else cls(*args,context)
            pc,ps=select(parent,proposer,pool,pspace,engine,method)
            invariance.append({'permutation':perm,'metric_equal':pspace.matrix()==space.matrix(),
                               'same_candidate':pc.key==candidate.key})
        proposal=q.add('R35_frozen_proposals',{'method':method,'parent':parent.json(),'previous':previous.json(),
            'pool':[b.json() for b in pool],'tasks':tasks,'context':context,'space':space.public(),
            'branches':{k:{'candidate':b.json(),'selection':s} for k,(b,s) in branches.items()},
            'invariance':invariance,'history_records':list(q.block_refs)},deps=(space.version,)+tuple(q.block_refs))
        newblocks=[];newrefs=[]
        for j in range(old.ADOPTION_BLOCKS):
            block,ref=q.acquire(old.opaque_problems(seed*100000+1000+gen*20+j));newblocks.append(block);newrefs.append(ref)
        ae=old.InterventionEngine(tasks,newblocks);successors={};adoptions={}
        # Primary first: record its own execution cost before auxiliary matched branches reuse caches.
        for name,(cand,_) in branches.items():
            successors[name],adoptions[name]=old.adoption(parent,cand,ae)
            if name=='primary':primary_adoption_cost=dict(ae.cost)
        child=successors['primary'];adopted=child.key!=parent.key
        check=q.add('R35_empirical_bundle_adoption',{'proposal':proposal,'checks':adoptions,'child':child.json(),
            'scope':'new finite bank; future distribution UNKNOWN','not_full_persistent_state_certification':True},deps=(proposal,)+tuple(newrefs))
        q.previous_allocator=parent;q.bind_allocator(child,(check,))
        chosen=ae.run(child,0).task;q.search_program=old.search.Program(tasks[chosen])
        task_binding=q.add('R35_actual_task_binding',{'before':oldtask,'after':q.search_program.ast,
            'allocator':child.json(),'used_by_next_opaque_diagnosis':True},deps=(q.bundle_permission,))
        if method in ('measured','plain') and successors['graph'].key!=child.key:raise RuntimeError('graph mismatch')
        # All choices frozen above. Only the external evaluator sees these future blocks.
        tests=[old.problems(seed*100000+5000+gen*20+j) for j in range(old.TEST_BLOCKS)]
        ev=old.InterventionEngine(tasks,tests)
        outcomes={name:[ev.run(b,j).loss for j in range(old.TEST_BLOCKS)]
                  for name,b in {'parent':parent,'child':child,**successors}.items()}
        means={k:mean(v) for k,v in outcomes.items()}
        delta=means['parent']-means['child'];gp=means['previous']-means['child'];gi=means['initial']-means['child']
        strict=gen>0 and previous_adoption and adopted and min(delta,gp,gi)>old.EPS
        spatial=q.causal_act(port,gen%2,(gen+4)%7)
        if not spatial['executed'] or not spatial['correct']:raise RuntimeError('learned causal controller failed')
        if identity!=(id(q),id(q.ledger)):raise RuntimeError('Queen or Ledger replaced')
        rounds.append({'generation':gen,'parent':parent.json(),'child':child.json(),'adopted':adopted,
            'previous_adopted':previous_adoption,'strict_empirical_link':strict,'delta':delta,'gamma_previous':gp,'gamma_initial':gi,
            'space':space.public(),'proposal_record':proposal,'check_record':check,'task_binding':task_binding,
            'invariance':invariance,'atlas_previous_overlap':overlap,'checks':adoptions,'branches':{k:b.key for k,(b,_) in branches.items()},
            'evaluation_only':{'means':means,'blocks':outcomes},'spatial_step':spatial,
            'primary_proposal_cost':primary_cost,'primary_adoption_cost':primary_adoption_cost,
            'auxiliary_proposal_cost':diff(engine.cost,primary_cost),'total_adoption_cost':dict(ae.cost),
            'evaluator_cost':dict(ev.cost),'proposal_interventions':engine.export(),'adoption_interventions':ae.export(),
            'finite_certificate':selection if method=='certified' else None})
        previous_adoption=adopted
        for block,ref in zip(newblocks,newrefs):q.remember(block,ref)
    sequence=sequence_check(controller,w.parameters,w.bias) if validate_words else {'status':'not separately repeated for this matched method'}
    # Actual allocator and effect-controller support withdrawal; historical references survive.
    root=newrefs[-1];old_body=q.ledger.records[root].body;q.ledger.revoke(root,'R36 allocator evidence withdrawn')
    stopped=False
    try:q.require_allocator()
    except PermissionError:stopped=True
    hist=q.add('R36_historical_reference',{'preserved':True},refs=(root,))
    closure_root=controller.rows[0]['observation'];closure_body=q.ledger.records[closure_root].body
    q.ledger.revoke(closure_root,'R36 actual transition evidence withdrawn');control_stopped=False
    try:q.causal_act(port,0,0)
    except PermissionError:control_stopped=True
    before=dict(w.cost);replacement,newcells=learn_closure(q,port,controller.rows)
    restored=q.causal_act(port,1,5)
    pressure={'allocator_stopped':stopped,'allocator_body_preserved':old_body==q.ledger.records[root].body,
        'reference_survives':hist not in q.ledger.invalid,'controller_stopped':control_stopped,
        'closure_body_preserved':closure_body==q.ledger.records[closure_root].body,
        'recovery_new_cells':newcells,'recovery_cost':diff(w.cost,before),'old_license_stays_invalid':controller.license in q.ledger.invalid,
        'new_control_correct':restored['executed'] and restored['correct'],'same_queen_ledger':identity==(id(q),id(q.ledger)),
        'recomputed_invalidity':q.ledger.recompute()==q.ledger.invalid,'allocator_root':root,'controller_root':closure_root,
        'recovery_control':restored,'new_controller':{'model':replacement.license,'binding':replacement.binding,'hash':replacement.model_hash}}
    summary={'updates':sum(r['adopted'] for r in rounds),'strict_links':sum(r['strict_empirical_link'] for r in rounds),
        'regressions':sum(r['delta'] < -old.EPS for r in rounds),'test_loss':mean(r['evaluation_only']['means']['child'] for r in rounds),
        'recursive_gain':mean(r['gamma_initial'] for r in rounds[1:]),'quotient_classes':len(set(controller.groups.values())),
        'closure_cells':cells,'memory_field_needed':bool(controller.memory_conflicts),'long_witness':controller.long_witness is not None,
        'metric_permutation_changes':sum(not a['metric_equal'] for r in rounds for a in r['invariance']),
        'proposal_permutation_changes':sum(not a['same_candidate'] for r in rounds for a in r['invariance']),
        'graph_candidate_equal':all(r['branches']['graph']==r['branches']['primary'] for r in rounds),
        'finite_exact_certificates':sum(r['finite_certificate'] is not None and r['finite_certificate']['status']=='EXACT' for r in rounds),
        'primary_model_interventions':sum(r['primary_proposal_cost'].get('interventions_executed',0)+r['primary_adoption_cost'].get('interventions_executed',0) for r in rounds),
        'primary_model_queries':sum(r['primary_proposal_cost'].get('simulated_queries',0)+r['primary_adoption_cost'].get('simulated_queries',0) for r in rounds),
        'all_controls_correct':all(r['spatial_step']['correct'] for r in rounds),
        'all_pressure_pass':all(pressure[k] for k in ('allocator_stopped','allocator_body_preserved','reference_survives','controller_stopped','closure_body_preserved','old_license_stays_invalid','new_control_correct','same_queen_ledger','recomputed_invalidity')) and newcells==1}
    return {'stage':'R35/R36','seed':seed,'method':method,'same_queen':True,'same_ledger':True,
        'source_lineage':'R31 -> R3 -> M54 Queen/M8 Ledger; unchanged inherited files',
        'fixture_evaluator_only':{'parameters':w.parameters,'bias':w.bias,'not_learner_inputs':True},
        'closure':closed,'closure_cost':closure_cost,'sequence_evaluation_only':sequence,
        'summary':summary,'rounds':rounds,'pressure':pressure,'actual_diagnostic_cost':asdict(q.own_diagnostic_cost),
        'world_cost':dict(w.cost),'ledger_read_cost':dict(q.cost),'ledger':q.ledger.export(),'invalid':sorted(q.ledger.invalid)}


def check_frozen():
    root=Path(__file__).resolve().parents[1]
    f=json.loads((root/'r32_r37/FROZEN.json').read_text())
    for p,h in f['sha256'].items():
        if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h:raise RuntimeError('frozen source changed: '+p)
    return root


def run(batch,start=0,end=16):
    root=check_frozen();out=root/'results/r32_r37'/batch;out.mkdir(parents=True,exist_ok=True)
    for seed in SEEDS[batch][start:end]:
        for method in METHODS:
            path=out/f'{seed}_{method}.json.xz'
            if path.exists():raise FileExistsError(path)
            t=time.perf_counter();r=episode(seed,method,method=='measured')
            raw=(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
            with path.open('xb') as file:file.write(lzma.compress(raw,preset=3))
            receipt={'file':path.name,'bytes':path.stat().st_size,'raw_bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),
                     'xz_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'elapsed_seconds':time.perf_counter()-t,'summary':r['summary']}
            (out/(path.stem+'.receipt.json')).write_text(json.dumps(receipt,indent=2))
            print(seed,method,json.dumps(r['summary']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',choices=SEEDS);p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=16)
    a=p.parse_args();run(a.batch,a.start,a.end)
