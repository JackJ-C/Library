"""Frozen finite research. All output stays in this Library workspace."""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import argparse,json,lzma,platform,sys,time
from library_m54.study import trajectory
from library_m54.queen import METHODS
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/m54_m57'
SOURCES=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'library_m54').glob('*.py'))]+[
    'library_m8/core.py','library_m8/__init__.py','run_m54_m57.py','tools/verify_m54_m57.py','docs/M54_M57_CONTRACT.md']

def sha(b):return sha256(b).hexdigest()
def encode(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def manifest():return {p:sha((ROOT/p).read_bytes()) for p in SOURCES}

def criterion(rows):
    main=[r for r in rows if r['method']=='library'];plain={r['seed']:r for r in rows if r['method']=='plain'}
    total=Counter()
    for r in main:total.update(r['counts'])
    checks={
        'continuous_three_revisions':all(r['counts']['same_instance'] and r['counts']['history_unchanged'] and r['counts']['post_boot_revisions']>=3 for r in main),
        'structural_expansion':all(r['counts']['structure_revisions']>=1 for r in main),
        'heldout_success_ge_98pct':total['future_correct']/total['future_total']>=.98,
        'every_stage_ge_95pct':all(sum(x['correct'] for x in s['future'])/len(s['future'])>=.95 for r in main for s in r['stages']),
        'unchanged_physics_zero_regression':total['regressions']==0,
        'separate_attribution':total['attribution_distinct_correct']==total['attribution_distinct_total'] and total['attribution_symmetric_correct']==total['attribution_symmetric_total'] and total['attribution_false_certain']==0,
        'anonymous_permutation':all(x['permutation_ok'] for r in main for x in r['attribution']),
        'plain_equivalent':all(r['counts']==plain[r['seed']]['counts'] and r['cost']==plain[r['seed']]['cost'] for r in main),
        'proof_withdrawal_and_recovery':all(r['permission_test'] and all(r['permission_test'][k] for k in ('ready','permission_lost','entries_blocked','world_not_changed_by_blocked_tasks','unrelated_calibration_preserved','regained')) for r in main),
        'history_actually_reduces_new_probes':all(x['same_object'] and x['with_history']['history_used']>0 and x['with_history']['cost']['probes']<x['without_history']['cost']['probes'] and all(sum(v['correct'] for v in x[k])/len(x[k])>=.98 for k in ('with_future','without_future')) for r in main if (x:=r['auxiliary_recovery']) is not None),
        'history_interventions_present':sum(r['auxiliary_recovery'] is not None for r in main)==2,
        'worker_and_self_separated':all(sum(c['component']=='Workers' for c in r['component_changes'])==1 and sum(c['component']=='own_emission' for c in r['component_changes'])==1 for r in main),
        'budgets_respected':all(not str(z.get('status')).startswith('budget:') for r in main for s in r['stages'] for z in s['repairs']),
        'new_condition_conflict_evidence':all(any(json.loads(rec['body']).get('same_command_conflicting_effects') is not None for rec in r['ledger'] if rec['kind']=='model_revision') for r in main),
    }
    return {'checks':checks,'joint_pass':all(checks.values())}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('freeze','A','B'));args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    f=OUT/'freeze.json'
    if args.phase=='freeze':
        if f.exists():raise RuntimeError('do not overwrite a frozen contract')
        data={'sources':manifest(),'A':list(range(22000,22008)),'B':list(range(23000,23008)),
              'development':[0,1,2,3],'local_freeze_only':True,'base':'a122a5c764bb04d87d2ee8b06ae57ee4a2e89cb4'}
        f.write_bytes(encode(data));print('FROZEN',sha(f.read_bytes()));return
    frozen=json.loads(f.read_bytes())
    if manifest()!=frozen['sources']:raise RuntimeError('frozen source mismatch')
    rows=[];timings=[]
    for method in METHODS:
        for i,seed in enumerate(frozen[args.phase]):
            t=time.perf_counter();r=trajectory(seed,method,confirm=True,auxiliary=i<2 and method in ('library','plain'))
            timings.append({'seed':seed,'method':method,'seconds':time.perf_counter()-t});rows.append(r)
            print(args.phase,method,seed,r['counts']['future_correct'],'/',r['counts']['future_total'],flush=True)
    summary={}
    for method in METHODS:
        c=Counter();cost=Counter();pc=Counter()
        for r in rows:
            if r['method']==method:c.update(r['counts']);cost.update(r['cost']);pc.update(r['physics_cost'])
        summary[method]={'counts':dict(c),'cost':dict(cost),'physics_cost':dict(pc)}
    result={'phase':args.phase,'python':platform.python_version(),'frozen_sha256':sha(f.read_bytes()),'source_sha256':manifest(),
            'summary':summary,'verdict':criterion(rows),'rows':rows}
    raw=encode(result);h=sha(raw);(OUT/'runs').mkdir(exist_ok=True)
    archive=OUT/'runs'/(h+'.json.xz')
    if archive.exists() and lzma.decompress(archive.read_bytes())!=raw:raise RuntimeError('collision')
    if not archive.exists():archive.write_bytes(lzma.compress(raw))
    (OUT/(args.phase+'.json')).write_bytes(encode({k:v for k,v in result.items() if k!='rows'}|{'archive':str(archive.relative_to(ROOT)),'raw_sha256':h}))
    (OUT/(args.phase+'_timing'+('_optimized' if not __debug__ else '')+'.json')).write_bytes(encode(timings))
    print('RESULT',args.phase,h,result['verdict'],flush=True)
    return 0 if result['verdict']['joint_pass'] else 2
if __name__=='__main__':sys.exit(main())
