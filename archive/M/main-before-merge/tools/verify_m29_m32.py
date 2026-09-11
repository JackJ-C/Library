"""独立数值重放和覆盖核验；不调用合成器或实验入口。"""
from collections import Counter,defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import lzma
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from library_m25.algebra import prove_builder,prove_search
from library_m29.proof import prove


def require(ok,message):
    if not ok:raise ValueError(message)


def pack(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def hashof(value):return sha256(pack(value)).hexdigest()


def ev(e,r):
    operation=e[0]
    if operation=='c':return int(e[1])
    if operation=='v':return r[e[1]]
    a=ev(e[1],r);b=ev(e[2],r)
    if operation=='+':return a+b
    if operation=='-':return a-b
    if operation=='*':return a*b
    if operation=='/':return Fraction(a,b)
    raise ValueError('invalid recorded syntax')


def value(builder,f,x,previous=None):
    r={'x':x,'fx':f(x),'f0':f(0),'f1':f(1)}
    if previous is not None:
        r.update(tx=value(previous,f,x),t0=value(previous,f,0),t1=value(previous,f,1))
    return ev(builder,r)


def violation(e,c):
    try:
        actual=ev(e,c['left'])
        expected=ev(e,c['right']) if 'right' in c else c['expected']
        return actual!=expected
    except (ValueError,ZeroDivisionError,KeyError):return True


def verify_bridge(data):
    builders=[r['expression'] for r in data['builders']]
    require(len(builders)==2,'two builders')
    refutations=0
    for i,row in enumerate(data['builders']):
        require(prove_builder(row['expression'],i,builders[0] if i else None)['passed'],'builder polynomial identity')
        cases=row['training_cases'];seen=set()
        for step in row['rounds']:
            require(seen<=set(step['active_before']),'lost counterexample')
            require(all(not violation(step['expression'],cases[j]) for j in step['active_before']),'candidate violates retained evidence')
            if step['counterexample']:
                j=step['counterexample']['id']
                require(violation(step['expression'],cases[j]),'false counterexample')
                seen.add(j);refutations+=1
        require(all(not violation(row['expression'],c) for c in cases),'final builder evidence')
    sr=data['search'];require(prove_search(sr['expression'])['passed'],'search law algebra')
    def bad(e,c):
        try:
            q=Fraction(ev(e,c['registers']))
            return q.denominator!=1 or c['slope']*(q-c['root'])!=0
        except (ValueError,ZeroDivisionError,KeyError):return True
    for step in sr['rounds']:
        require(all(not bad(step['expression'],sr['training_cases'][j]) for j in step['active_before']),'search lost evidence')
        if step['counterexample']:
            require(bad(step['expression'],sr['training_cases'][step['counterexample']['id']]),'false search counterexample')
            refutations+=1
    require(all(not bad(sr['expression'],c) for c in sr['training_cases']+sr['validation_cases']),'search validation')
    freeze=hashof(dict(builders=builders,search=sr['expression']))
    require(freeze==data['frozen_metaprograms'] and data['learning_unchanged_after_transfer'],'meta-learning changed during transfer')
    totals=defaultdict(Counter);coverage=defaultdict(set);outputs=0
    for row in data['transfer_rows']:
        tag=row['variant'];m=row['metadata'];key=(m['seed'],m['family'])
        require(key not in coverage[tag],'duplicate case');coverage[tag].add(key)
        d=m['shift'];family=m['family']
        def base(x):
            if family==0:return (x-d)**3
            if family==1:return (x-d)**4
            if family==2:return abs(x-d)+x*x
            return (x-d)//3+x%2+x*x*x
        def rawf(x):return base(x)+m['drift']*x+m['bias']
        def target(x):
            z=base(0);delta=base(1)-z
            return m['coefficient']*(base(x)-z-x*delta)+m['offset']+m['linear']*x
        use_builder=tag not in ('no_builder','neither')
        def tool(x):return value(builders[1],rawf,x,builders[0]) if use_builder else rawf(x)
        measurements=dict(row['measurements'])
        require(all(target(x)==y for x,y in measurements.items()),'incorrect raw evidence')
        require(not set(row['future_x']) & set(measurements),'future leakage')
        require(row['future_x']==[x for x in range(-16,17) if x not in measurements],'future coverage')
        diagnostic=next(x for x in (2,3,4,-1,-2) if tool(x)!=0)
        for p,r in row['query_trace']:
            require(r==p*tool(diagnostic)+measurements[0]+diagnostic*(measurements[1]-measurements[0])-target(diagnostic),'wrong residual')
        require(row['parameter_queries']==len(row['query_trace']),'query cost mismatch')
        expected=[target(x) for x in row['future_x']]
        require(expected==row['expected'],'wrong held-out reference')
        if row['accepted']:
            p=row['proposed'];y0,y1=measurements[0],measurements[1]
            actual=[p*tool(x)+y0+x*(y1-y0) for x in row['future_x']]
            require(actual==row['actual'],'recorded execution differs from independent replay')
            require(row['instance_preserved'] and row['binding_changed'],'no deployment')
            require(hashof(row['context'])==row['certificate'],'invalid certificate')
            require(all(a==b for _,a,b in row['validation']),'accepted failed validation')
            outputs+=len(actual)
        else:require(not row['actual'] and row['certificate'] is None,'rejection mistaken for deployment')
        correct=sum(a==b for a,b in zip(row['actual'],expected))
        regressions=sum(b==0 and a!=b for a,b in zip(row['actual'],expected))
        require(correct==row['correct'] and regressions==row['regressions'],'result count')
        c=totals[tag];c['tasks']+=1;c['accepted']+=row['accepted']
        c['all_future_correct']+=row['accepted'] and correct==len(expected)
        c['future_cases']+=len(expected);c['future_correct']+=correct
        c['parameter_queries']+=len(row['query_trace']);c['oracle_points']+=len(measurements)
        c['regressions']+=regressions
    expected_coverage={(s,f) for s in range(1000,1064) for f in range(4)}
    for tag in totals:
        require(coverage[tag]==expected_coverage,'missing cases: '+tag)
        require(dict(totals[tag])==data['transfer_summary'][tag],'summary differs: '+tag)
    require(len(totals)==8,'missing controls')
    return {'transfer_rows':len(data['transfer_rows']),'independently_replayed_outputs':outputs,'meta_refutations':refutations}


def independent(program, case, kind):
    fuel=[20000]
    def go(p,i):
        fuel[0]-=1
        if fuel[0]<0 or i>100:raise ValueError('nonterminating or unguarded program')
        op=p[0];empty=i >= (case['n'] if kind=='find' else len(case['xs']))
        if op=='empty':return go(p[1] if empty else p[2],i)
        if kind=='find':
            if op=='none':return None
            if op=='here':
                if empty:raise ValueError('empty head')
                return i
            if op=='hit':
                if empty:raise ValueError('empty predicate')
                return go(p[1] if case['mask']&(1<<i) else p[2],i)
        else:
            if op=='nil':return []
            if op=='raw':return case['xs'][i:]
            if op=='mapped':
                if empty:raise ValueError('empty mapped head')
                return case['mapping'][str(case['xs'][i])]
            if op=='join':return go(p[1],i)+go(p[2],i)
        if op=='recur':return go(program,i+1)
        raise ValueError('unknown opcode')
    try:
        actual=go(program,0)
        expected=next((i for i in range(case['n']) if case['mask']&(1<<i)),None) if kind=='find' else [y for x in case['xs'] for y in case['mapping'][str(x)]]
        return actual==expected
    except (ValueError,RecursionError):return False


def check():
    summary=json.loads((ROOT/'results/m29_m32/summary.json').read_bytes())
    archive=(ROOT/summary['archive']).resolve()
    require(archive.is_relative_to(ROOT/'results/m29_m32/runs'),'archive outside this experiment')
    raw=lzma.decompress(archive.read_bytes())
    require(sha256(raw).hexdigest()==summary['result_sha256'],'raw archive')
    record=json.loads(raw);data=record['data']
    for name,key in record['source_sha256'].items():
        path=(ROOT/name).resolve()
        require(path.is_relative_to(ROOT),'source outside repository')
        require(sha256(path.read_bytes()).hexdigest()==key,'source mismatch '+name)
    require(record['tests_run']==len(record['test_names']) and not record['failures'] and not record['errors'] and not record['skipped'],'tests')
    require(len(data['generations'])==3 and all(data['seed_calls_blocked']),'handoff coverage')
    discoveries=[data['bootstrap']]+[g['discoveries'] for g in data['generations']]
    refutations=0
    for generation,items in enumerate(discoveries):
        for kind,row in items.items():
            require(prove(row['program'],kind)['passed'],'induction')
            require(hashof(row['program'])==row['program_sha256'],'kernel fingerprint')
            if generation:
                require(data['generations'][generation-1]['parents'][kind]==discoveries[generation-1][kind]['program_sha256'],'parent provenance')
                require(row['origin']=='generated_search_and_expansion','hidden seed path')
            seen=set()
            for step in row['rounds']:
                require(seen<=set(step['active_before']),'discarded counterexample')
                c=step['counterexample']
                if c:
                    require(not independent(step['program'],c['detail']['case'],kind),'false refutation')
                    seen.add(c['id']);refutations+=1
    challenges=0
    for kind,rows in data['challenges'].items():
        require({r['seed'] for r in rows}==set(range(1000,1064)),'challenge seeds')
        for r in rows:
            require(independent(data['bootstrap'][kind]['program'],r['case'],kind),'challenge replay')
            challenges+=1
    transfer=verify_bridge(data['bridge'])
    require(hashof(data['bridge']['transfer_rows'])==data['baseline']['rows_sha256'],'fresh baseline equality')
    neg=data['negative_results']
    require(neg['latent_accepted'] and neg['latent_errors']==[13],'hidden failure')
    require(neg['new_guard_denies_obsolete_execution'] and not neg['certificate_valid_after_rebind'],'execution gate')
    require(neg['wrong_vm_output']!=neg['wrong_vm_expected'] and neg['wrong_predicate_selected']!=neg['true_required_candidate'],'trusted boundary failures')
    require(len(neg['shuffled'])==64 and all(r['actual']==r['expected'] for r in neg['shuffled']),'permutations')
    require(all(r['rejected'] and not r['valid_after_change'] for r in neg['changed_bindings']),'binding changes')
    require(record['strong_goal']=='NOT_ESTABLISHED' and data['origin_coverage']['fixed_high_level_dependencies'],'no universal upgrade')
    return dict(status='VERIFIED',archive_sha256=summary['result_sha256'],kernel_discoveries=8,
                actual_kernel_refutations=refutations,challenge_replays=challenges,**transfer,
                strong_goal='NOT_ESTABLISHED',files=len(record['source_sha256']))


if __name__=='__main__':
    result=check();(ROOT/'results/m29_m32/verification.json').write_bytes(pack(result))
    print(json.dumps(result,sort_keys=True,ensure_ascii=False))
