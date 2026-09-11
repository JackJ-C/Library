"""M45–M48: local pre-validation freeze, independent trajectory batches, immutable results."""
from pathlib import Path
from hashlib import sha256
import argparse,io,json,lzma,platform,sys,unittest
from library_m45.study import batch,pressures
from library_m45.core import canonical
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/m45_m48'
BASE=['library_m8/__init__.py','library_m8/core.py','library_m12/__init__.py','library_m12/core.py',
      'library_m37/__init__.py','library_m37/core.py','library_m37/identity.py','library_m37/world.py',
      'library_m41/__init__.py','library_m41/integration.py']
SOURCES=BASE+['library_m45/'+p.name for p in sorted((ROOT/'library_m45').glob('*.py'))]+[
    'run_m45_m48.py','tools/verify_m45_m48.py']
SEEDS={'dev':list(range(8)),'A':list(range(5000,5032)),'B':list(range(6000,6032))}


def manifest():return {p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def verdict(data,pressure):
    c=data['summary']['library'];n=len(data['seeds'])
    main=[r for r in data['rows'] if r['method']=='library']
    post=[t for r in main for s in r['stages'] if s['learning'] for t in s['future']]
    by={(r['seed'],r['method']):r for r in data['rows']}
    equal=lambda m:all([x['correct'] for s in by[(seed,'library')]['stages'] for x in s['future']]==
                      [x['correct'] for s in by[(seed,m)]['stages'] for x in s['future']] for seed in data['seeds'])
    checks={
      'same_queen_history_and_three_revisions':all(r['counts']['same_object'] and r['counts']['history_preserved'] and r['counts']['at_least_three_revisions'] for r in main),
      'future_success_ge_90pct':c['future_correct']/c['future_tasks']>=.90,
      'post_inference_no_wrong_execution':all(not t['executed'] or t['correct'] for t in post),
      'post_inference_coverage_ge_95pct':sum(t['correct'] for t in post)/len(post)>=.95,
      'true_source_never_excluded':c['ownership_true_included']==c['ownership_cases'],
      'unique_source_never_wrong':c['ownership_unique_correct']==c['ownership_unique'],
      'same_information_plain_matches':equal('plain'),
      'strong_model_marginal_matches':equal('marginal'),
      'causal_cut_changes_action_coverage_ge_30pp':c['causal_factual_correct']/c['causal_factual_total']-c['causal_remove_source_constraints_correct']/c['causal_remove_source_constraints_total']>=.30,
      'restored_binding_matches_factual':c['causal_restore_correct']==c['causal_factual_correct'],
      'evidence_withdrawal_blocks_and_recovers':all(all(r['gate'].values()) for r in main),
      'same_effect_echo_ambiguous_and_usable':pressure['echo_equal']['source_options']==[0,1,2] and all(t['correct'] for t in pressure['echo_equal']['test']),
      'different_effect_echo_no_wrong_execution':pressure['echo_different']['source_options']==[0,1,2] and all(not t['executed'] or t['correct'] for t in pressure['echo_different']['test']),
      'outside_family_failure_recorded':pressure['unseen_state_dependence']['actual_error'] and not pressure['unseen_state_dependence']['licence_after_observed_error'],
    }
    return {'checks':checks,'bounded_pass':all(checks.values()),
        'unconditional_self_identity':False,'open_ended_unknown_mechanism_repair':False,
        'explicit_identity_label_necessary':False,'global_novelty_established':False}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['dev','freeze','A','B'])
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.phase=='freeze':
        path=OUT/'freeze.json'
        if path.exists():raise RuntimeError('freeze already exists')
        frozen={'baseline_repo':'JackJ-C/Library','baseline_commit':'a107e655e5a5c4d9dd00a3032ee8d190c8eea4a6',
            'sources':manifest(),'seeds':SEEDS,'contract_sha256':sha256((ROOT/'docs/M45_M48_CONTRACT.md').read_bytes()).hexdigest(),
            'registration':'local before validation; remote write unavailable in this session'}
        path.write_text(json.dumps(frozen,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
        print('FREEZE_SHA256',sha256(path.read_bytes()).hexdigest());return 0
    if args.phase!='dev':
        f=json.loads((OUT/'freeze.json').read_text())
        if f['sources']!=manifest():raise RuntimeError('frozen source mismatch')
        if f['contract_sha256']!=sha256((ROOT/'docs/M45_M48_CONTRACT.md').read_bytes()).hexdigest():raise RuntimeError('contract changed')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromName('library_m45.tests'))
    (OUT/(args.phase+'_tests.log')).write_text(stream.getvalue())
    if not result.wasSuccessful() or result.skipped:raise RuntimeError('tests failed')
    data=batch(SEEDS[args.phase]);p=pressures()
    report={'milestones':'M45-M48','phase':args.phase,'python':platform.python_version(),'source_sha256':manifest(),
        'tests_run':result.testsRun,'batch':data,'pressure':p,'verdict':verdict(data,p)}
    raw=(canonical(report)+'\n').encode();h=sha256(raw).hexdigest();runs=OUT/'runs';runs.mkdir(exist_ok=True)
    path=runs/(h+'.json.xz')
    if path.exists() and lzma.decompress(path.read_bytes())!=raw:raise RuntimeError('archive collision')
    if not path.exists():path.write_bytes(lzma.compress(raw))
    summary={k:v for k,v in report.items() if k!='batch'}
    summary.update(archive=str(path.relative_to(ROOT)),sha256=h,raw_bytes=len(raw),
                   compressed_bytes=path.stat().st_size,summary=data['summary'])
    (OUT/(args.phase+'.json')).write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'phase':args.phase,'sha256':h,'verdict':report['verdict'],'bytes':len(raw)},ensure_ascii=False))
    return 0 if report['verdict']['bounded_pass'] else 2

if __name__=='__main__':sys.exit(main())
