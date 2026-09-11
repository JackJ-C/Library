"""R4–R7 bounded validation; no network, secrets, other repository or background job.
Output is defined prospectively: detailed records for all seeds; full ledger for
first primary seed of each cohort. Deterministic replays are not extra samples.
"""
from pathlib import Path
from hashlib import sha256
import argparse,json,lzma,platform,sys,unittest,io
from r4_r7.study import lineage,summarize,stress,METHODS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/r4_r7'
PHASES={'A':list(range(7100,7108)), 'B':list(range(8100,8108))}
OLD=['src/__init__.py','src/core.py','vendor/library_m54/__init__.py','vendor/library_m54/queen.py',
     'vendor/library_m54/grammar.py','vendor/library_m54/world.py','vendor/library_m8/__init__.py','vendor/library_m8/core.py']
NEW=['r4_r7/__init__.py','r4_r7/lifecycle.py','r4_r7/search.py','r4_r7/monitor.py','r4_r7/study.py',
     'r4_r7/tests.py','run_r4_r7.py','tools/verify_r4_r7.py']

def enc(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def hashes():return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in OLD+NEW}

def compact(rows,first):
    catalog={}
    def intern(p):
        h=sha256(enc(p)).hexdigest();catalog[h]=p;return h
    for e in rows:
        if e['method']!='recursive' or e['seed']!=first:e['ledger']=None
        for case in e['heldout_cases']:case['problem']=intern(case['problem'])
        for r in e['rounds']:
            for case in r['live']:case['problem']=intern(case['problem'])
            for field in ('current_replays','counter_replays'):
                if field in r['evaluation_only']:
                    r['evaluation_only'][field]=[x['price'] for x in r['evaluation_only'][field]]
    return catalog

def gates(rows,summary,pressure):
    es=[r for r in rows if r['method']=='recursive'];n=len(es);m=summary['metacognition']
    basics={
        'all_current_self_stress_pass':all(pressure['nonlinear_self'][k] for k in ('observed_mismatch','history_still_readable','worker_preserved','world_preserved','task_stays_closed','recovery_after_condition_removed')),
        'same_instance_all_phases':all(e['same_queen'] for e in rows),
        'monitor_withdrawal_all':all(all(e['monitor_withdrawal'].values()) for e in es),
        'matched_raw_first_order':len({a['raw_correct'] for a in m.values()})==1,
        'restoration_and_rename_equal':m['own']==m['restored']==m['renamed'],
        'same_information_plain_equal':all(next(x for x in rows if x['seed']==e['seed'] and x['method']=='plain')['final_test_cost']==e['final_test_cost'] for e in es),
    }
    recursion={
        'at_least_quarter_lineages_two_consecutive_causal_links':sum(e['consecutive_links'] for e in es)>=n/4,
        'positive_mean_paired_benefit_ci':summary['recursive_mean_delta_ci'][0]>0,
        'final_solver_at_least_25pct_better_than_initial':summary['search']['recursive']['final_test_cost'] <= .75*summary['search']['fixed_query']['final_test_cost']}
    functional={
        'reliability_brier_better_than_blind':m['own']['mean_brier'] <= m['blind']['mean_brier']-.01,
        'reliability_auc_at_least_60pct':m['own']['mean_type2_auc']>=.60,
        'same_quota_completion_gain_at_least_2pct':summary['metacognition_mean_gain']>=.02,
        'positive_trajectory_paired_gain_ci':summary['metacognition_gain_ci'][0]>0,
        'donor_reliability_model_worse':m['own']['mean_brier']<m['transplant']['mean_brier']}
    return {'integrity':basics,'recursive_enhancement':recursion,'functional_metacognition':functional,
            'integrity_pass':all(basics.values()),'recursive_pass':all(recursion.values()),
            'metacognition_pass':all(functional.values()) and all(basics.values()),
            'subjective_experience':'not_established_by_this_assay; no numerical consciousness probability'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('freeze','dev','A','B'));args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    freeze=OUT/'FROZEN.json'
    if args.phase=='freeze':
        if freeze.exists():raise RuntimeError('refuse overwrite of frozen protocol')
        state={'base_R':'1a7d6e548149a0d69e2cc2c22ddedbdc8314dbec','sources':hashes(),
               'phases':PHASES,'development_seeds':list(range(8)),
               'contract_sha256':sha256((ROOT/'docs/R4_R7_CONTRACT.md').read_bytes()).hexdigest()}
        freeze.write_bytes(enc(state));print(json.dumps(state,indent=2));return
    if args.phase!='dev':
        state=json.loads(freeze.read_bytes())
        if hashes()!=state['sources']:raise RuntimeError('frozen program changed')
        if sha256((ROOT/'docs/R4_R7_CONTRACT.md').read_bytes()).hexdigest()!=state['contract_sha256']:raise RuntimeError('contract changed')
    seeds=[0,1] if args.phase=='dev' else PHASES[args.phase]
    old=json.loads((ROOT/'FROZEN.json').read_bytes())['sources']
    for p,h in old.items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise RuntimeError('old frozen source changed: '+p)
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName('r4_r7.tests')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (OUT/(args.phase+'_tests.log')).write_text(stream.getvalue())
    if not result.wasSuccessful():print(stream.getvalue());raise RuntimeError('test failure')
    rows=[]
    for seed in seeds:
        for method in METHODS:
            row=lineage(seed,method,True);rows.append(row)
        print('completed paired lineage',seed,flush=True)
    summary=summarize(rows);press=stress();criteria=gates(rows,summary,press)
    report={'phase':args.phase,'seeds':seeds,'python':platform.python_version(),'sources':hashes(),
            'tests':result.testsRun,'criteria':criteria,'summary':summary,'pressure':press,'rows':rows,
            'record_scope':'All recorded candidates, paid probes, forecasts and scores; full ledger for first primary lineage only'}
    report['problem_catalog']=compact(rows,seeds[0])
    data=enc(report);h=sha256(data).hexdigest();out=OUT/'runs';out.mkdir(exist_ok=True)
    p=out/(args.phase+'_'+h+'.json.xz')
    if p.exists() and lzma.decompress(p.read_bytes())!=data:raise RuntimeError('archive collision')
    if not p.exists():p.write_bytes(lzma.compress(data,preset=9))
    metadata={k:v for k,v in report.items() if k not in ('rows','problem_catalog')}
    metadata.update(archive=str(p.relative_to(ROOT)),raw_sha256=h,raw_bytes=len(data),compressed_bytes=p.stat().st_size)
    (OUT/(args.phase+'_summary.json')).write_bytes(enc(metadata))
    print(json.dumps({'phase':args.phase,'raw_sha256':h,'compressed_bytes':p.stat().st_size,'criteria':criteria},indent=2))

if __name__=='__main__':main()
