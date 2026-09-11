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


def check(path=None):
    summary=json.loads((ROOT/'results/m25_m28/summary.json').read_bytes())
    path=ROOT/summary['archive'] if path is None else Path(path)
    raw=lzma.decompress(path.read_bytes())
    require(sha256(raw).hexdigest()==summary['result_sha256'],'raw archive digest')
    record=json.loads(raw);data=record['data']
    for name,key in record['source_sha256'].items():
        require(sha256((ROOT/name).read_bytes()).hexdigest()==key,'source changed: '+name)
    require(record['tests_run']==len(record['test_names']) and not record['errors'] and not record['failures'],'test record')
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
    require(freeze==data['frozen_metaprograms'] and data['learning_unchanged_after_transfer'],'learning state changed')
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
    neg=data['stress'];require(neg['latent_accepted'] and neg['latent_errors']==[13],'negative result lost')
    require(all(not a['accepted'] for a in neg['context_attacks']),'bad context accepted')
    return dict(status='VERIFIED',archive_sha256=summary['result_sha256'],
                files=len(record['source_sha256']),transfer_rows=len(data['transfer_rows']),
                independently_replayed_outputs=outputs,real_meta_refutations=refutations,
                formal_obligations=8,all_variants_coverage_verified=True)


if __name__=='__main__':
    result=check()
    (ROOT/'results/m25_m28/verification.json').write_bytes(pack(result))
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
