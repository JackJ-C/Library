"""Synchronous per-trajectory wrapper; frozen selection and verification code unchanged."""
import argparse, json, sys, time, lzma
from pathlib import Path
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from r20_r23_recovery.run import source_manifest,write_result,ci,PHASES,RESULTS
from r20_r23_recovery.integrity import canonical
from r20_r23_recovery.study import episode
from r20_r23_recovery.verify import verify_record


def check_sources():
    f=json.loads((RESULTS/'FROZEN_V2.json').read_text())
    if source_manifest()!=f['sources']:raise RuntimeError('frozen source mismatch')
    if sha256((ROOT/'docs/R20_R23_RECOVERY_CONTRACT.md').read_bytes()).hexdigest()!=f['contract_sha256']:
        raise RuntimeError('contract mismatch')


def one(phase,seed,optimized=False):
    if seed not in PHASES[phase]:raise ValueError('not a frozen validation seed')
    check_sources();start=time.monotonic()
    original=RESULTS/(phase+'_'+str(seed)+'.json')
    old=json.loads(original.read_text()) if original.exists() else None
    if old and not optimized:raise FileExistsError('preserve completed trajectory; use verify or optimized replay')
    r=episode(seed);p=episode(seed,'plain');p['method']='recursive'
    if canonical(r)!=canonical(p):raise AssertionError('plain trajectory not equal')
    counts=verify_record(r)
    raw=(canonical(r)+'\n').encode();h=sha256(raw).hexdigest()
    if old:
        if old['sha256']!=h:raise AssertionError('fresh replay differs')
        receipt=old
    else:receipt=write_result(r,phase+'_'+str(seed))
    mode='optimized' if optimized else 'normal'
    extra={'phase':phase,'seed':seed,'mode':mode,'sha256':h,'plain_actual_run_equal':True,
           'independent_replay':counts,'frozen_sources_match':True,
           'elapsed_seconds_not_a_scientific_metric':time.monotonic()-start}
    (RESULTS/f'{phase}_{seed}_{mode}_check.json').write_text(json.dumps(extra,indent=2)+'\n')
    print(json.dumps({**receipt,**extra}),flush=True)


def aggregate(phase):
    check_sources();runs=[]
    for seed in PHASES[phase]:
        r=json.loads((RESULTS/f'{phase}_{seed}.json').read_text())
        c=json.loads((RESULTS/f'{phase}_{seed}_normal_check.json').read_text())
        if r['sha256']!=c['sha256'] or not c['plain_actual_run_equal']:raise AssertionError('receipt mismatch')
        raw=lzma.decompress((ROOT/r['path']).read_bytes())
        if sha256(raw).hexdigest()!=r['sha256']:raise AssertionError('raw mismatch')
        r['plain_actual_run_equal']=True;runs.append(r)
    g=ci([r['gain'] for r in runs]);k=ci([r['calibration_gain'] for r in runs])
    checks={'6_of_8_consecutive':sum(r['consecutive'] for r in runs)>=6,
            '7_of_8_without_regression':sum(r['regressions']==0 for r in runs)>=7,
            'recursive_gain_ci_positive':g[0]>0,'calibration_gain_ci_positive':k[0]>0}
    out={'phase':phase,'cohort':PHASES[phase],'unit':'whole trajectory','runs':runs,
         'recursive_gain_ci':g,'calibration_gain_ci':k,'checks':checks,
         'stable_recursive_pass':all(checks[x] for x in checks if x!='calibration_gain_ci_positive'),
         'coupling_pass':checks['calibration_gain_ci_positive'],'subjective_experience_identified':False}
    (RESULTS/f'{phase}_SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='runs'}))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('phase',choices=PHASES);a.add_argument('seeds',type=int,nargs='*')
    a.add_argument('--aggregate',action='store_true');args=a.parse_args()
    if args.aggregate:aggregate(args.phase)
    else:
        for s in args.seeds:one(args.phase,s,sys.flags.optimize>0)
