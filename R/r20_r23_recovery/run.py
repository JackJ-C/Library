"""Finite synchronous phase runner with per-trajectory commits/checkpoints.
Does not download, read credentials, invoke shells, or edit any legacy artifact.
"""
from pathlib import Path
from hashlib import sha256
from random import Random
import argparse,json,lzma,time
from .study import episode
from .integrity import canonical

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results/r20_r23_recovery'
PHASES={'A':list(range(27100,27108)),'B':list(range(28100,28108))}


def source_manifest():
    paths=[]
    for name in ('r20_r23_recovery','r12_r15','r4_r7','src','vendor'):
        paths+=sorted((ROOT/name).rglob('*.py'))
    return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}


def write_result(row,name):
    data=(canonical(row)+'\n').encode();h=sha256(data).hexdigest()
    path=RESULTS/'runs'/(h+'.json.xz');path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if lzma.decompress(path.read_bytes())!=data:raise RuntimeError('hash collision')
    else:path.write_bytes(lzma.compress(data))
    receipt={'name':name,'sha256':h,'path':str(path.relative_to(ROOT)),'bytes':len(data),'compressed':path.stat().st_size,
             'seed':row['seed'],'updates':row['updates'],'strict_links':row['strict_links'],
             'consecutive':row['consecutive'],'regressions':row['regressions'],
             'gain':row['gain'],'calibration_gain':row['calibration_gain']}
    (RESULTS/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def ci(values):
    rng=Random(92023);n=len(values)
    a=sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(5000))
    return [a[124],a[4874]]


def phase(phase_name):
    frozen=json.loads((RESULTS/'FROZEN_V2.json').read_text())
    if source_manifest()!=frozen['sources']:raise RuntimeError('source differs from recovery freeze')
    protocol=ROOT/'docs/R20_R23_RECOVERY_CONTRACT.md'
    if sha256(protocol.read_bytes()).hexdigest()!=frozen['contract_sha256']:raise RuntimeError('contract changed')
    summaries=[]
    for seed in PHASES[phase_name]:
        started=time.monotonic();r=episode(seed);p=episode(seed,'plain');p['method']='recursive'
        if canonical(p)!=canonical(r):raise AssertionError('same-information baseline disagrees')
        receipt=write_result(r,phase_name+'_'+str(seed))
        receipt['plain_actual_run_equal']=True;summaries.append(receipt)
        print(json.dumps({'phase':phase_name,**receipt,'runtime_seconds_not_scientific':round(time.monotonic()-started,3)}),flush=True)
    gainci=ci([r['gain'] for r in summaries]);calci=ci([r['calibration_gain'] for r in summaries])
    checks={'6_of_8_consecutive':sum(r['consecutive'] for r in summaries)>=6,
            '7_of_8_without_regression':sum(r['regressions']==0 for r in summaries)>=7,
            'recursive_gain_ci_positive':gainci[0]>0,'calibration_gain_ci_positive':calci[0]>0}
    result={'phase':phase_name,'cohort':PHASES[phase_name],'unit':'whole trajectory','runs':summaries,
            'recursive_gain_ci':gainci,'calibration_gain_ci':calci,'checks':checks,
            'stable_recursive_pass':all(checks[k] for k in checks if k!='calibration_gain_ci_positive'),
            'coupling_pass':checks['calibration_gain_ci_positive'],'subjective_experience_identified':False}
    (RESULTS/(phase_name+'_SUMMARY.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=PHASES)
    args=ap.parse_args();print(json.dumps(phase(args.phase)))
