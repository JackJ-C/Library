"""Run a whole frozen lineage at a time, with separate immutable checkpoints.
All generated files remain below this R/ directory; no network or external services.
"""
import sys,os,json,lzma,copy,platform
from pathlib import Path
from hashlib import sha256
from dataclasses import asdict
from collections import Counter
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
os.environ.setdefault('PYTHONDONTWRITEBYTECODE','1')
from r12_r15.study import stream,METHODS,summarize_stream,resample_interval
from r12_r15.meta import lineage

PHASES={'dev':list(range(4)),'A':list(range(11100,11108)),'B':list(range(12100,12108))}
OUT=ROOT/'results/r12_r15'
META_METHODS=('coupled','frozen_parent','unguarded','fixed_margin')


def data_bytes(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(x):return sha256(x).hexdigest()
def source_map():
    paths=list((ROOT/'r12_r15').glob('*.py'))+[ROOT/'run_r12_r15.py',ROOT/'tools/verify_r12_r15.py']
    old=json.loads((ROOT/'results/r4_r7/FROZEN.json').read_text())['sources']
    paths += [ROOT/p for p in old if p.endswith('.py')]
    return {str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in sorted(set(paths))}

def check_frozen():
    f=json.loads((OUT/'FROZEN.json').read_text())
    if f['sources']!=source_map():raise RuntimeError('frozen source mismatch')
    if f['contract_sha256']!=digest((ROOT/'docs/R12_R15_CONTRACT.md').read_bytes()):raise RuntimeError('contract changed')
    return f

def run_one(phase,seed):
    if seed not in PHASES[phase]:raise ValueError('seed outside declared phase')
    freeze=check_frozen() if phase!='dev' else None
    online=[];q=w=None
    for method in METHODS:
        row,candidate,world=stream(seed,method,keep_queen=True)
        online.append(row)
        if method=='adaptive':q,w=candidate,world
    # The primary actually continues the same object; comparators start from matched snapshots.
    qid,lid=id(q),id(q.ledger)
    controls={m:(copy.deepcopy(q),copy.deepcopy(w)) for m in META_METHODS if m!='coupled'}
    meta=[]
    primary=lineage(q,w,seed,'coupled',True)
    primary['continued_from_online']=id(q)==qid and id(q.ledger)==lid
    meta.append(primary)
    for method in META_METHODS[1:]:
        other,world=controls[method]
        meta.append(lineage(other,world,seed,method))
    result={'phase':phase,'seed':seed,'python':platform.python_version(),'sources':source_map(),
            'online':online,'meta':meta,'freeze_contract':None if freeze is None else freeze['contract_sha256'],
            'scope':'bounded online reliability plus conservative recursive successor experiment'}
    raw=data_bytes(result);h=digest(raw)
    runs=OUT/'runs';runs.mkdir(parents=True,exist_ok=True)
    target=runs/(h+'.json.xz')
    if target.exists() and lzma.decompress(target.read_bytes())!=raw:raise RuntimeError('hash collision')
    if not target.exists():target.write_bytes(lzma.compress(raw))
    pointer={'phase':phase,'seed':seed,'sha256':h,'archive':str(target.relative_to(ROOT)),
             'bytes':len(raw),'compressed_bytes':target.stat().st_size}
    file=OUT/f'{phase}_{seed}.json'
    if file.exists() and file.read_bytes()!=data_bytes(pointer):raise RuntimeError('refuse overwriting a different phase result')
    file.write_bytes(data_bytes(pointer))
    print(json.dumps(pointer),flush=True)
    return result

def summarize(phase):
    rows=[]
    for seed in PHASES[phase]:
        p=json.loads((OUT/f'{phase}_{seed}.json').read_text())
        raw=lzma.decompress((ROOT/p['archive']).read_bytes())
        if digest(raw)!=p['sha256']:raise RuntimeError('raw hash mismatch')
        rows.append(json.loads(raw))
    online=summarize_stream([e for r in rows for e in r['online']])
    meta={}
    for method in META_METHODS:
        es=[e for r in rows for e in r['meta'] if e['method']==method]
        gains=[e['paired_gain'] for e in es]
        meta[method]={'n':len(es),'accepted':sum(e['accepted'] for e in es),
             'strict_links':sum(e['strict_links'] for e in es),'consecutive_lineages':sum(e['consecutive'] for e in es),
             'regressions':sum(e['regressions'] for e in es),'regression_free_lineages':sum(e['regressions']==0 for e in es),
             'final_cost':sum(e['final_cost'] for e in es),'hand_cost':sum(e['hand_baseline_cost'] for e in es),
             'initial_cost':sum(e['initial_baseline_cost'] for e in es),
             'paired_gain':sum(gains)/len(gains),'paired_ci':resample_interval(gains),
             'guard_changed_acceptance':sum(not rr['primary']['accepted'] and rr['unguarded_counter']['accepted'] for e in es for rr in e['rounds']),
             'cost':{k:sum(e['cost'][k] for e in es) for k in es[0]['cost']}}
    n=len(rows);a=online['methods']['adaptive'];pair=online['paired'];m=meta['coupled']
    checks={
      'prediction_adaptation':pair['frozen']['brier_improvement']>=.01 and pair['frozen']['brier_ci'][0]>0,
      'behavioral_benefit_vs_frozen':pair['frozen']['gain']>=.005 and pair['frozen']['gain_ci'][0]>0,
      'timely_drift_detection':a['detected_changes']>=.75*a['total_changes'],
      'limited_false_alarms':a['false_alarms']<=n,
      'same_information_and_inlined_equivalence':all(pair[k]['gain']==0 and pair[k]['brier_improvement']==0 for k in ('plain','compiled')),
      'recursive_majority_consecutive':m['consecutive_lineages']>=.75*n,
      'recursive_positive_paired_effect':m['paired_ci'][0]>0,
      'recursive_mostly_no_regression':m['regression_free_lineages']>=.875*n,
      'same_object_continuation':all(r['meta'][0]['continued_from_online'] for r in rows)}
    result={'phase':phase,'seed_count':n,'online':online,'meta':meta,'checks':checks,
            'functional_prediction_pass':checks['prediction_adaptation'],
            'online_joint_pass':all(checks[k] for k in ('prediction_adaptation','behavioral_benefit_vs_frozen','timely_drift_detection','limited_false_alarms')),
            'stable_recursive_pass':all(checks[k] for k in ('recursive_majority_consecutive','recursive_positive_paired_effect','recursive_mostly_no_regression')),
            'subjective_experience':'NOT_IDENTIFIED_BY_THIS_PROTOCOL',
            'phenomenal_scope':'No direct probability assigned; matched statistical controller is not known to be non-conscious.'}
    (OUT/f'{phase}_SUMMARY.json').write_bytes(data_bytes(result))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('dev','A','B','freeze'));ap.add_argument('--seed',type=int);ap.add_argument('--summary',action='store_true')
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.phase=='freeze':
        p=OUT/'FROZEN.json'
        if p.exists():raise RuntimeError('frozen registration already exists')
        f={'base_commit':'36a8dc4a978e8352d2be50ae834f90ebf4915f8b','sources':source_map(),
           'contract_sha256':digest((ROOT/'docs/R12_R15_CONTRACT.md').read_bytes()),'phases':PHASES,
           'start_commit':'275e8e99aa5bedf40aafd4a359b8b6eca346b2bd'}
        p.write_bytes(data_bytes(f));print(p.read_text());return
    if args.summary:summarize(args.phase)
    elif args.seed is not None:run_one(args.phase,args.seed)
    else:raise ValueError('use one declared seed or --summary, not an implicit background run')
if __name__=='__main__':main()
