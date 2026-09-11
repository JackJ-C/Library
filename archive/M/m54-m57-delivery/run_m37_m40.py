"""开发→冻结→两批独立种子验证。仅标准库；结果内容寻址保存。"""
from pathlib import Path
from hashlib import sha256
import argparse,io,json,lzma,platform,sys,unittest
from library_m37.study import run_batch
from library_m37.pressure import run as pressure
from library_m37.core import canonical

ROOT=Path(__file__).resolve().parent
NEW=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'library_m37').glob('*.py'))]
BASE=['library_m12/__init__.py','library_m12/core.py','library_m8/__init__.py','library_m8/core.py']
SOURCES=NEW+BASE+['run_m37_m40.py','tools/verify_m37_m40.py']


def manifest():return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def verdict(batch):
    n=len(batch['seeds']);c=batch['summary']['library']
    es=batch['episodes'];paired={}
    for e in es:
        if e['method'] in ('library','plain'):paired.setdefault(e['seed'],{})[e['method']]=e
    equal=all(v['library']['counts']==v['plain']['counts'] and
              v['library']['budget_cost']==v['plain']['budget_cost'] and
              [r['future'] for r in v['library']['rows']]==[r['future'] for r in v['plain']['rows']]
              for v in paired.values())
    budgets=all(all(r['audit']['budget'][k]<=r['audit']['budget']['max_'+k]
                   for k in ('reads','probes','comparisons')) for e in es for r in e['rows'] if r['audit'])
    checks={
        'same_object_three_cycles':c.get('same_queen',0)==n and c.get('cycles_at_least_three',0)==n,
        'historical_slices_unchanged':c.get('history_preserved',0)==n,
        'cause_and_patch_correct':c.get('wrong_patch_sets',0)==0 and c['events_resolved']==c['events'],
        'future_task_rate_ge_95pct':c['future_correct']/c['future_tasks']>=.95,
        'after_review_future_all_correct':c['post_review_correct']==c['post_review_tasks'],
        'no_unrelated_patch_or_regression':c.get('unrelated_modifications',0)==0 and c.get('regressions',0)==0,
        'control_model_ge_95pct':c['control_correct']/c['control_checks']>=.95,
        'identifiable_attribution_ge_95pct':c.get('identity_correct',0)/c['identity_identifiable']>=.95,
        'indistinguishable_attribution_uncertain':c['ambiguity_calibrated']==c['identity_ambiguous'] and c['false_certainty']==0,
        'anonymous_order_equivariant':c['identity_equivariance_pass']==c['identity_equivariance_checks'],
        'reference_and_proof_dependency_separated':c['reference_dependency_consistent']==n,
        'same_lifetime_rollback_and_gate':all(all(e['post_episode_pressure'].values())
                                            for e in es if e['method']=='library'),
        'same_information_plain_comparison':equal,'uniform_caps_respected':budgets,
    }
    return {'checks':checks,'joint_pass':all(checks.values())}


def store(report,name):
    data=(canonical(report)+'\n').encode();h=sha256(data).hexdigest()
    out=ROOT/'results/m37_m40';(out/'runs').mkdir(parents=True,exist_ok=True)
    p=out/'runs'/(h+'.json.xz')
    if p.exists() and lzma.decompress(p.read_bytes())!=data:raise RuntimeError('archive mismatch')
    if not p.exists():p.write_bytes(lzma.compress(data))
    summary={k:v for k,v in report.items() if k not in ('batch','pressure')}
    if 'batch' in report:
        summary['results']=report['batch']['summary'];summary['budget_cost']=report['batch']['budget_cost']
        summary['physical_cost']=report['batch']['physical_cost']
    summary.update(archive=str(p.relative_to(ROOT)),sha256=h,bytes=len(data),compressed_bytes=p.stat().st_size)
    (out/(name+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'name':name,'sha256':h,'verdict':report.get('verdict'),'compressed':p.stat().st_size},ensure_ascii=False))
    return h


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('dev','freeze','A','B'))
    args=ap.parse_args();out=ROOT/'results/m37_m40';out.mkdir(parents=True,exist_ok=True)
    freeze=out/'freeze.json'
    if args.phase=='freeze':
        if freeze.exists():raise RuntimeError('freeze already exists; do not overwrite')
        contract=ROOT/'docs/M37_M40_CONTRACT.md'
        if not contract.exists():raise RuntimeError('contract missing')
        state={'sources':manifest(),'contract_sha256':sha256(contract.read_bytes()).hexdigest(),
               'A_seeds':list(range(1000,1032)),'B_seeds':list(range(2000,2032)),
               'thresholds':'docs/M37_M40_CONTRACT.md','development_seeds':list(range(8))}
        freeze.write_text(json.dumps(state,sort_keys=True,indent=2)+'\n');print(sha256(freeze.read_bytes()).hexdigest());return 0
    if args.phase=='dev':seeds=list(range(8))
    else:
        frozen=json.loads(freeze.read_text())
        if frozen['sources']!=manifest():raise RuntimeError('source differs from frozen validation code')
        if frozen['contract_sha256']!=sha256((ROOT/'docs/M37_M40_CONTRACT.md').read_bytes()).hexdigest():raise RuntimeError('contract changed')
        seeds=frozen[args.phase+'_seeds']
    suite=unittest.defaultTestLoader.loadTestsFromName('library_m37.tests')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/(args.phase+'_tests.log')).write_text(stream.getvalue())
    if not r.wasSuccessful():print(stream.getvalue());return 1
    batch=run_batch(seeds)
    report={'milestone':'M37-M40','phase':args.phase,'python':platform.python_version(),
            'tests_run':r.testsRun,'tests_passed':r.wasSuccessful(),'source_sha256':manifest(),
            'verdict':verdict(batch),'batch':batch,'pressure':pressure(),
            'validation_frozen':args.phase!='dev','scope':'finite continuous self-diagnosis plus conditional historical attribution'}
    store(report,args.phase)
    return 0 if report['verdict']['joint_pass'] else 2


if __name__=='__main__':sys.exit(main())
