"""Independent recorded-evidence checks. Does not import Queen or its learner."""
from pathlib import Path
from collections import Counter,defaultdict,deque
from itertools import product
import hashlib,json,lzma

ROOT=Path(__file__).resolve().parents[1]

def require(ok,why):
    if not ok:raise AssertionError(why)


def ledger_check(records):
    invalid=set();children=defaultdict(set);diagnoses=0
    for i,r in enumerate(records):
        require(r['seq']==i,'sequence')
        require(all(type(j)is int and 0<=j<i for j in r['refs']+r['deps']),'edge direction')
        for j in r['deps']:
            require(j not in invalid,'new proof uses revoked evidence');children[j].add(i)
        b=json.loads(r['body'])
        if r['kind']=='revocation':
            todo=deque([b['root']]);new=[]
            while todo:
                k=todo.popleft()
                if k in invalid:continue
                invalid.add(k);new.append(k);todo.extend(children[k])
            require(sorted(new)==b['invalidated'],'revocation closure')
        if r['kind']=='R_prospective_self':
            require(all(j not in invalid for j in r['refs']),'forecast despite withdrawn license')
        if r['kind']=='R_review':
            H=list(product(range(1,7),range(7),range(7),range(1,7)))
            for st in b['steps']:
                kind,a=st['query'];observed=tuple(st['observed']);keys=st['evidence']
                rr=[json.loads(records[k]['body']) for k in keys]
                if kind=='self': require(observed==(rr[1]['issued'],) and a==rr[0]['requested'],'own probe evidence')
                elif kind=='cal': require(observed==tuple(rr[0]['readings']) and rr[0]['anchor']==a,'calibration evidence')
                else:
                    before=rr[0]['before']['workers'];after=rr[1]['after']['workers'];obj=rr[0]['object']
                    value=(rr[0]['issued'],)+tuple((after[j][obj]-before[j][obj])%7 for j in (0,1))
                    require(value==observed,'motor evidence')
                filtered=[]
                for s,b0,b1,g in H:
                    value=((s*a)%7,) if kind=='self' else ((a+b0)%7,(a+b1)%7) if kind=='cal' else (s*a%7,g*s*a%7,g*s*a%7)
                    if value==observed:filtered.append((s,b0,b1,g))
                require(len(H)==st['before'] and len(filtered)==st['after'],'inference trajectory')
                H=filtered
            require(H==[tuple(b['identified'])],'diagnostic conclusion');diagnoses+=1
    return diagnoses


def check(phase):
    summary=json.loads((ROOT/'results'/f'{phase}_summary.json').read_text())
    raw=lzma.decompress((ROOT/'results'/summary['archive']).read_bytes())
    require(hashlib.sha256(raw).hexdigest()==summary['raw_sha256'],'result hash')
    report=json.loads(raw);frozen=json.loads((ROOT/'FROZEN.json').read_text())
    require(report['source_sha256']==frozen['sources'],'frozen test program')
    require(report['seeds']==frozen[phase],'seed cohort')
    for path,sha in frozen['sources'].items():require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,'changed '+path)
    counts=Counter();byseed={}
    for e in report['episodes']:
        byseed.setdefault(e['seed'],{})[e['method']]=e
        for row in e['timeline']:
            step=row['step'];s,b0,b1,g=row['truth'];obj=row['step'].get('object')
            if step['executed']:
                require(step['forecast']<step['intention']<step['observation'],'forecast came after observation')
                require(step['issued']==s*step['request']%7,'actual own command')
                p=(step['before'][0][obj]-b0)%7
                end=(p+g*step['issued'])%7
                require((step['observed'][0][obj]-b0)%7==end,'physical effect')
                require(row['success_gold_only']==(end==step['goal']),'online score')
            else:require(not row['success_gold_only'],'blocked success')
            counts['online_checks']+=1
        cc=Counter()
        for assay in e['assays']:
            for row in assay['rows']:
                s,g,p,goal=row['inferred_self'],row['inferred_world'],row['position'],row['goal']
                for mode,a,issued,after,good in row['modes']:
                    options=range(1,7) if mode=='removed' else [s%6+1] if mode=='swapped' else [s]
                    possible={((goal-p)*pow(v*g,-1,7))%7 for v in options}
                    expected=next(iter(possible)) if len(possible)==1 else None
                    require(a==expected,'intervened planner')
                    require(issued==(None if a is None else row['gold_self']*a%7),'assay own output')
                    require(after==(p if a is None else (p+row['gold_world']*issued)%7),'assay world')
                    require(good==(a is not None and after==goal),'assay success')
                    cc[mode+'_correct']+=good;cc[mode+'_total']+=1;counts['assay_cells']+=1
        for k,v in cc.items():require(e['counts'][k]==v,'assay aggregation')
        for r in e['origins']:
            require(r['symmetric']==[.5,.5],'symmetric overclaim');require(r['equivariant'],'alias order')
            require(r['distinct'][r['truth']]==1,'record-match attribution');counts['origin_checks']+=1
        for m in e['meta']:
            a,b=m['primary'],m['frozen_parent_counterfactual']
            require(a['proposed_asts']==b['proposed_asts'],'different candidate worlds')
            require(a['fully_evaluated']==b['fully_evaluated']<=6,'unmatched meta budget')
            require(a['actual_policy_rebound']==a['accepted'],'fake code update');counts['meta_pairs']+=1
        if e['ledger'] is not None:counts['diagnostic_replays']+=ledger_check(e['ledger'])
    for seed,methods in byseed.items():
        require(methods['evolve']['counts']==methods['plain']['counts'],'plain control mismatch')
        require(methods['evolve']['actual_cost']==methods['plain']['actual_cost'],'plain cost mismatch')
    st=report['stress']['nonlinear_self']
    require(st['initially_licensed'] and st['future']['mismatch'] and st['revoked_after_counterexample'],'missing stress failure')
    require(not st['relicensed_by_inadequate_recheck'],'known counterexample forgotten')
    return {'phase':phase,'status':'VERIFIED','raw_sha256':summary['raw_sha256'],**counts}


if __name__=='__main__':
    report={'status':'VERIFIED','independent':'separate checker implementation, not a separate laboratory','phases':[check(p) for p in 'AB']}
    (ROOT/'results/VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
