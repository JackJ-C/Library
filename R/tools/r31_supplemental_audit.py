"""Post-freeze, read-only R31 archive audit.

Does not import the learner, run experiments, alter the frozen verifier, or feed
analysis back to Queen. It adds linkage and derived-field checks missing from
that verifier. The declared fixture generator and its PRNG remain trusted.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import lzma
import math
from pathlib import Path
from random import Random
from statistics import mean
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from r28_r31.verify import (verify_episode, reference_intervention, diagnostic,
                           evaluate, ast_size, equal)
from r28_r31.space import digest, freeze
from r4_r7.search import make_problem

SHADOWS = ('graph', 'raw', 'shuffled', 'collapsed', 'previous', 'initial')
INITIAL = {'ast': ['-', 'mean', 'uncert'], 'scale': 1.0}
INITIAL['key'] = digest([INITIAL['ast'], INITIAL['scale']])


def need(condition, message):
    if not condition:
        raise ValueError(message)


def same(actual, expected, message):
    need(equal(actual, expected), message)


def finite(x):
    if isinstance(x, float):
        need(math.isfinite(x), 'nonfinite archive value')
    elif isinstance(x, dict):
        for v in x.values(): finite(v)
    elif isinstance(x, (tuple, list)):
        for v in x: finite(v)


def fixture(seed):
    rng = Random(seed)
    out = []
    for _ in range(6):
        p, h = make_problem(rng.randrange(1 << 50), n=16, nq=12)
        out.append(({'masks': p.masks, 'prices': p.prices, 'count': p.count}, h))
    return out


def diagnostic_cost(p, ast, trace):
    """Count all informative alternatives and feature evaluations, not just chosen ones."""
    available = list(range(len(p['masks'])))
    ops = features = 0
    for row in trace:
        before = row['before']
        n = before.bit_count()
        for query in available:
            sizes = [(m & before).bit_count() for m in p['masks'][query]]
            features += len(sizes) + 3
            if (n*n-sum(s*s for s in sizes))*1024//(n*n) > 0:
                ops += ast_size(ast)
        available.remove(row['query'])
    return {'ast': ops, 'features': features, 'queries': len(trace),
            'price': sum(r['price'] for r in trace)}


class AuditEngine:
    """Reference arithmetic with independently accounted cache/call schedule."""
    def __init__(self, tasks, blocks):
        self.tasks, self.blocks = tasks, blocks
        self.task_cache, self.response_cache = {}, {}
        self.cost = Counter()

    def task(self, arm, block, case):
        self.cost['task_loss_requests'] += 1
        key = arm, block, case
        if key in self.task_cache:
            self.cost['task_cache_hits'] += 1
            return self.task_cache[key]
        p, h = self.blocks[block][case]
        price, rem, trace = diagnostic(p, h, self.tasks[arm])
        c = diagnostic_cost(p, self.tasks[arm], trace)
        self.cost.update({'simulated_queries': c['queries'],
                          'task_ast_ops': c['ast'], 'task_feature_ops': c['features'],
                          'simulated_query_price': price})
        response = (price/(9*len(p['masks'])) if rem.bit_count()==1 else 1.0,
                    tuple((r['query'], r['value'], r['price']) for r in trace))
        self.task_cache[key] = response
        return response

    def run(self, bundle, block):
        self.cost['intervention_requests'] += 1
        key = bundle['key'], block
        if key in self.response_cache:
            self.cost['intervention_cache_hits'] += 1
            return self.response_cache[key]
        self.cost['interventions_executed'] += 1
        ref = reference_intervention(bundle, self.tasks, self.blocks[block])
        self.cost['allocation_ast_ops'] += (12-len(self.tasks))*len(self.tasks)*ast_size(bundle['ast'])
        for arm, index, loss in ref['requests']:
            same(self.task(arm, block, index%4)[0], loss, 'counted task request mismatch')
            self.cost['loss_requests'] += 1
        for j in (4, 5): self.task(ref['task'], block, j)
        self.response_cache[key] = ref
        return ref

    def average(self, bundle, indices):
        return mean(self.run(bundle, j)['loss'] for j in indices)

    def export(self):
        return [{'bundle': k[0], 'block': k[1], **v}
                for k, v in sorted(self.response_cache.items())]


def geometry(columns):
    rows = [() for _ in columns[0]]
    axes, splits, counts = [], [], []
    for j, col in enumerate(columns):
        new = [old+(freeze(c['signature']),) for old, c in zip(rows, col)]
        a, b = len(set(rows)), len(set(new))
        if j==0 or b>a:
            axes.append(j); rows=new; counts.append((a,b))
            if b>a: splits.append([j,a,b])
    return rows, axes, splits, counts


def groups_and_distances(rows, mode):
    if mode=='shuffled': rows=rows[1:]+rows[:1]
    if mode=='collapsed': rows=[rows[0]]*len(rows)
    names={}
    groups=[names.setdefault(x,len(names)) for x in rows]
    d=[[sum(a!=b for a,b in zip(x,y))/len(x) for y in rows] for x in rows]
    return groups,d


def reference_proposal(pool, proposer, signatures, engine, mode):
    pilots=list(range(min(3,len(engine.blocks)-1)))
    checks=list(range(len(pilots),len(engine.blocks)))
    losses=[[engine.run(b,j)['loss'] for j in pilots] for b in pool]
    means=[mean(x) for x in losses]; minimum=min(means)
    groups,d=groups_and_distances(signatures,mode)
    use=mode!='raw'; selected=[]; used=set(); ranking=[]
    for _ in range(2):
        eligible=[i for i in range(1,len(pool)) if i not in selected]
        if use:
            novel=[i for i in eligible if groups[i] not in used]
            if novel: eligible=novel
        entries=[]
        for i in eligible:
            variance=mean((v-means[i])**2 for v in losses[i])
            u=math.sqrt((variance+.0001)/len(pilots))
            if use: u+=.025*min(d[i][j] for j in [0]+selected)
            x=(means[i],proposer['scale']*u,len(pilots)/(len(pilots)+len(checks)),means[i]-minimum)
            score=evaluate(proposer['ast'],x)
            engine.cost['allocation_ast_ops']+=ast_size(proposer['ast'])
            entries.append((score,ast_size(pool[i]['ast']),pool[i]['key'],i,x))
        winner=min(entries);i=winner[3];selected.append(i);used.add(groups[i])
        ranking.append({'eligible':eligible,'chosen':i,
                        'priorities':[[p[3],p[0],p[4]] for p in entries]})
    scored=[(engine.average(pool[i],checks),0 if i==0 else 1,ast_size(pool[i]['ast']),pool[i]['key'],i)
            for i in [0]+selected]
    index=min(scored)[-1]
    return pool[index],{'mode':mode,'proposer':proposer,'pilot_means':means,
                       'shortlist':selected,'proposal':index,
                       'scores':[[x[-1],x[0]] for x in scored], 'ranking':ranking,
                       'logical_full_checks':len(selected)*len(checks)}


def reference_adopt(parent, candidate, engine):
    old=[engine.run(parent,j)['loss'] for j in range(4)]
    new=[engine.run(candidate,j)['loss'] for j in range(4)]
    gain=mean(old)-mean(new)
    accepted=candidate['key']!=parent['key'] and gain>.002
    return candidate if accepted else parent,{
        'accepted':accepted,'old':old,'new':new,'certificate':{
            'scope':'exact observed finite adoption bank, not future distribution',
            'independent_blocks':4,'empirical_gain':gain,
            'hoeffding_single_comparison_lcb':gain-math.sqrt(2*math.log(2/.05)/4),
            'distribution_certificate':'UNKNOWN'}}


def audit_episode(x):
    finite(x)
    base=verify_episode(x)
    records=x['ledger'];bodies=[json.loads(r['body']) for r in records]
    blocks={i:[(v['problem'],v['inferred']) for v in b['cases']]
            for i,(r,b) in enumerate(zip(records,bodies)) if r['kind']=='R30_observed_block'}
    seeds=[x['seed']*100000+j for j in range(3)]
    for g in range(6):
        seeds.append(x['seed']*100000+100+g)
        seeds.extend(x['seed']*100000+1000+g*20+j for j in range(4))
    need(len(blocks)==len(seeds),'wrong acquired block count')
    own=Counter()
    for (i,block),seed in zip(blocks.items(),seeds):
        same(block,fixture(seed),'actual block differs from declared opaque fixture')
        support=[]
        for row in bodies[i]['cases']:
            intention=row['intention'];receipt=row['receipt']
            need(intention<receipt<i,'block receipt ordering')
            support.extend([intention,receipt])
            ib,rb=bodies[intention],bodies[receipt]
            same(row['problem'],ib['problem'],'block/intention problem linkage')
            need(rb['intention']==intention,'receipt/intention linkage')
            need(rb['inferred_mechanism']==row['inferred'],'block/receipt inference linkage')
            c=diagnostic_cost(ib['problem'],ib['program'],rb['transcript'])
            own.update({'actual_queries':c['queries'],'paid_probe_cost':c['price'],
                        'ast_ops':c['ast'],'feature_ops':c['features']})
        same(records[i]['deps'],support,'block support linkage')
    need(Counter(x['actual_cost'])==own,'complete opaque query cost mismatch')
    binds={}
    for i,r in enumerate(records):
        if r['kind']=='R30_allocator_binding': binds[i]=bodies[i]
    parent=INITIAL;previous=INITIAL;last_adopt=False;old_task=0
    hist=list(blocks)[:3];block_ids=list(blocks);facts=[];all_cost=Counter()
    for g,r in enumerate(x['rounds']):
        need(r['generation']==g,'generation index mismatch')
        pr,cr=r['proposal_record'],r['check_record'];p=bodies[pr];ch=bodies[cr]
        same(r['parent'],parent,'actual allocator continuity')
        same(p['parent'],parent,'proposal parent continuity')
        same(p['previous'],previous,'previous proposer continuity')
        same(p['tasks'][0],old_task,'task candidate parent continuity')
        next_block=block_ids[3+5*g]
        hist=(hist+[next_block])[-6:]
        same(p['history_records'],hist,'exact prior history view')
        tasks=p['tasks'];pool=p['pool']
        need(len(pool)==8 and len(tasks)==6,'wrong candidate counts')
        same(pool[0],parent,'pool parent identity')
        pe=AuditEngine(tasks,[blocks[k] for k in hist])
        columns=[[pe.run(b,j) for b in pool] for j in range(min(3,len(hist)-1))]
        signatures,axes,splits,counts=geometry(columns)
        groups,_=groups_and_distances(signatures,'space')
        same(r['space'],p['space'],'space round/proposal linkage')
        sp=r['space'];coords=sp['coordinate_records']
        need(len(coords)==len(axes),'coordinate count')
        expected={'dimension':len(axes),'axes':axes,'classes':len(set(groups)),
                  'groups':groups,'splits':splits,'coordinate_records':coords,'space_record':sp['space_record']}
        same(sp,expected,'witness coordinates or equivalence classes mismatch')
        for axis,key,(a,b) in zip(axes,coords,counts):
            cb=bodies[key]
            same(cb['responses'],columns[axis],'coordinate responses not grounded in execution')
            same(cb['bundle_ids'],[v['key'] for v in pool],'coordinate intervention identity')
            same(records[key]['deps'],[hist[axis]],'coordinate support linkage')
            need(cb['axis']==axis and cb['classes_before']==a and cb['classes_after']==b,'coordinate split claim')
        same(records[sp['space_record']]['deps'],coords,'space certificate linkage')
        same(records[pr]['deps'],[sp['space_record']]+hist,'proposal certificate linkage')
        primary_proposer=INITIAL if x['mode']=='frozen' else parent
        actual_mode='raw' if x['mode']=='raw' else 'space'
        names=['primary']+list(SHADOWS);proposals={}
        for name in names:
            if name=='primary': proposer,mode=primary_proposer,actual_mode
            else:
                proposer=previous if name=='previous' else INITIAL if name=='initial' else parent
                mode='space' if name in ('previous','initial') else name
            candidate,choice=reference_proposal(pool,proposer,signatures,pe,mode)
            same(p['branches'][name],{'candidate':candidate,'selection':choice},'unverified proposal ranking: '+name)
            proposals[name]=candidate
        same(pe.export(),r['proposal_interventions'],'proposal cache records')
        need(pe.cost==Counter(r['proposal_cost']),'proposal logical/AST/query cost mismatch')
        fresh_ids=block_ids[4+5*g:8+5*g]
        same(records[cr]['deps'],[pr]+fresh_ids,'complete check evidence linkage')
        need(all(k>pr for k in fresh_ids),'adoption before proposal freeze')
        ae=AuditEngine(tasks,[blocks[k] for k in fresh_ids]);succ={};checks={}
        for name in names: succ[name],checks[name]=reference_adopt(parent,proposals[name],ae)
        same(ch['checks'],checks,'check losses not linked to executed responses')
        same(r['checks'],checks,'round/ledger check linkage')
        same(ch['deployed'],succ['primary'],'deployment/check linkage')
        same(ch['proposal_record'],pr,'check/proposal linkage')
        child=succ['primary'];adopted=child['key']!=parent['key']
        same(r['child'],child,'actual child not approved child')
        bind_id=cr+1;need(records[bind_id]['kind']=='R30_allocator_binding','missing immediate allocator binding')
        same(bodies[bind_id]['bundle'],child,'actual complete bundle binding')
        same(records[bind_id]['deps'],[cr],'binding support')
        chosen=ae.run(child,0)['task']
        tb=bind_id+1;need(records[tb]['kind']=='R30_actual_task_binding','task not bound after allocator')
        same(bodies[tb]['before'],old_task,'task before state')
        same(bodies[tb]['after'],tasks[chosen],'actual selected task not bound')
        same(bodies[tb]['allocator'],child,'task allocator linkage')
        same(records[tb]['deps'],[bind_id],'task binding support')
        same(ae.export(),r['adoption_interventions'],'adoption cache records')
        need(ae.cost==Counter(r['adoption_cost']),'adoption logical/AST/query cost mismatch')
        eb=[fixture(x['seed']*100000+5000+g*20+j) for j in range(6)]
        ee=AuditEngine(tasks,eb)
        tested={'parent':parent,'child':child,**succ}
        values={name:[ee.run(b,j)['loss'] for j in range(6)] for name,b in tested.items()}
        means={name:mean(v) for name,v in values.items()}
        same(r['evaluation_only'],{'means':means,'blocks':values},'evaluation means/block linkage')
        need(ee.cost==Counter(r['evaluator_cost']),'evaluator cost mismatch')
        delta=means['parent']-means['child'];gp=means['previous']-means['child'];gi=means['initial']-means['child']
        strict=g>0 and last_adopt and adopted and min(delta,gp,gi)>1e-12
        fields={'adopted':adopted,'previous_adopted':last_adopt,'strict_empirical_link':strict,
                'delta':delta,'gamma_previous':gp,'gamma_initial':gi,
                'geometry_changes_proposal':proposals['raw']['key']!=proposals['primary']['key'],
                'graph_proposal_identical':proposals['graph']['key']==proposals['primary']['key'],
                'wrong_association_changes_proposal':proposals['shuffled']['key']!=proposals['primary']['key']}
        for k,v in fields.items(): same(r[k],v,'derived round claim: '+k)
        all_cost.update(pe.cost);all_cost.update(ae.cost);all_cost.update(ee.cost)
        facts.append({**fields,'test':means,'dimension':len(axes),'classes':len(set(groups))})
        parent,previous,old_task,last_adopt=child,parent,tasks[chosen],adopted
        hist=(hist+fresh_ids)[-6:]
    flags=[r['strict_empirical_link'] for r in facts]
    summary={'updates':sum(r['adopted'] for r in facts),'strict_empirical_links':sum(flags),
             'adjacent_links':any(a and b for a,b in zip(flags,flags[1:])),
             'regressions':sum(r['delta'] < -1e-12 for r in facts),
             'mean_test_loss':mean(r['test']['child'] for r in facts),
             'mean_recursive_gain':mean(r['gamma_initial'] for r in facts[1:]),
             'mean_geometry_gain':mean(r['test']['raw']-r['test']['child'] for r in facts),
             'mean_dimension':mean(r['dimension'] for r in facts),
             'mean_classes':mean(r['classes'] for r in facts),
             'changed_proposals':sum(r['geometry_changes_proposal'] for r in facts),
             'graph_identical':all(r['graph_proposal_identical'] for r in facts)}
    same(x['summary'],summary,'aggregate summary not derived from raw execution')
    need(x['pressure']['withdrawn_root'] in x['invalid'],'withdrawn root missing')
    need(bind_id in x['invalid'],'final allocator binding not actually invalidated')
    # Functional exception behavior is covered by frozen execution tests, not inferable from a boolean alone.
    return {'seed':x['seed'],'mode':x['mode'],'passed':True,
            'frozen_reference':base,'derived_summary':summary,
            'recounted_actual':dict(own),'recounted_all_engines_including_shadows_and_evaluation':dict(all_cost),
            'additional_checked_rounds':len(facts),
            'scope_exclusions':['not another research team','no full spatial-engine replay',
                                'candidate generator and PRNG are trusted','ledger read/geometry overhead not full CPU accounting']}


def run(root=ROOT/'results'/'r28_r31', limit=None):
    root=Path(root); receipts=[]; completed=0
    audit_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cache=root/'recovery'/'audit_cells';cache.mkdir(parents=True,exist_ok=True)
    for p in sorted(root.glob('[AB]/*.json.xz')):
        xz=p.read_bytes();raw=lzma.decompress(xz)
        raw_sha=hashlib.sha256(raw).hexdigest();xz_sha=hashlib.sha256(xz).hexdigest()
        checkpoint=cache/(p.name+'.audit.json')
        receipt=None
        if checkpoint.exists():
            old=json.loads(checkpoint.read_text())
            if old.get('audit_source_sha256')==audit_sha and old.get('raw_sha256')==raw_sha and old.get('xz_sha256')==xz_sha:
                receipt=old
        if receipt is None:
            if limit is not None and completed>=limit: continue
            audited=audit_episode(json.loads(raw))
            receipt={'file':str(p.relative_to(root)),'raw_sha256':raw_sha,'xz_sha256':xz_sha,
                     'audit_source_sha256':audit_sha,**audited}
            checkpoint.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
            completed+=1
            print('AUDITED',p.name,flush=True)
        receipts.append(receipt)
    if limit is None: need(len(receipts)==48,'expected complete 48 formal archives')
    return {'status':'POST_FREEZE_READ_ONLY_AUDIT','all_passed':len(receipts)==48 and all(r['passed'] for r in receipts),
            'archive_count':len(receipts),'frozen_sources_changed':False,
            'audit_source_sha256':audit_sha,'receipts':receipts}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'results/r28_r31/SUPPLEMENTAL_AUDIT.json')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args(); result=run(limit=args.limit)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='receipts'},ensure_ascii=False))
