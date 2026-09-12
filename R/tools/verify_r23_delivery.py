"""Read-only verification of complete R23 recovery artifacts.
No Queen, learner, candidate generator, or mutable allocator is imported.
"""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import argparse, json, lzma, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from r20_r23_recovery.verify import verify_record, eq, text
RESULTS=ROOT/'results/r20_r23_recovery'


def check(ok, why):
    if not ok: raise AssertionError(why)


def verify(phase):
    f=json.loads((RESULTS/'FROZEN_V2.json').read_text())
    for p,h in f['sources'].items():
        check(sha256((ROOT/p).read_bytes()).hexdigest()==h,'frozen source changed: '+p)
    check(sha256((ROOT/'docs/R20_R23_RECOVERY_CONTRACT.md').read_bytes()).hexdigest()==f['contract_sha256'],'contract changed')
    summary=json.loads((RESULTS/(phase+'_SUMMARY.json')).read_text())
    check(summary['cohort']==f['phases'][phase],'cohort changed')
    checks=[];total=Counter()
    for receipt in summary['runs']:
        p=ROOT/receipt['path']
        if not p.exists():raise FileNotFoundError('Full raw archive is required, not only its summary: '+str(p))
        raw=lzma.decompress(p.read_bytes())
        check(sha256(raw).hexdigest()==receipt['sha256'],'raw SHA mismatch')
        row=json.loads(raw);check(row['seed']==receipt['seed'],'wrong seed')
        counts=verify_record(row);updates=links=regressions=0;flags=[]
        for step in row['rounds']:
            for value in step['evaluation_only'].values():
                check(eq(value['mean'],sum(value['parts'])/len(value['parts'])),'mean not derived from its parts')
                total['checked_means']+=1
            update=text(step['primary']['parent'])!=text(step['primary']['after'])
            check(update==step['allocator_rebound'],'binding/update flag')
            parent,child,frozen=(step['evaluation_only'][s]['mean'] for s in ('parent','child','frozen_child'))
            link=step['generation']>0 and update and child<parent-1e-12 and child<frozen-1e-12
            reg=child>parent+1e-12
            check(link==step['strict_link'] and reg==step['regression'],'causal/regression flag')
            updates+=update;links+=link;regressions+=reg;flags.append(link)
        check((updates,links,regressions)==(row['updates'],row['strict_links'],row['regressions']),'aggregate flags')
        check(row['consecutive']==any(a and b for a,b in zip(flags,flags[1:])),'consecutive count')
        for mode in ('normal','optimized'):
            r=json.loads((RESULTS/f'{phase}_{row["seed"]}_{mode}_check.json').read_text())
            check(r['sha256']==receipt['sha256'] and r['plain_actual_run_equal'],'run receipt mismatch')
        total.update(counts)
        checks.append({'seed':row['seed'],'sha256':receipt['sha256'],'verified':True})
    check(len(checks)==8 and len({r['seed'] for r in checks})==8,'missing/repeated trajectory')
    return {'phase':phase,'verified':True,'sources':len(f['sources']),'trajectories':checks,'arithmetic_counts':dict(total),
            'scope':'Independently replayed finite computations; not an independent research team or phenomenology test'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('A','B','both'),default='both')
    args=parser.parse_args()
    for phase in ('AB' if args.phase=='both' else args.phase):
        result=verify(phase)
        (RESULTS/f'{phase}_FINAL_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
