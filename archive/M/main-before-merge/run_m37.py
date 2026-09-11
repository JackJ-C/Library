"""M37 corrected evidence-dependency validation, preserving A/B untouched. All output stays under results/m33_m36/."""
from pathlib import Path
from hashlib import sha256
import argparse
import json
import lzma
import platform
import unittest
from library_m33.study import batch, pressure_cases
import library_m33.study as study
from library_m37.grounded import GroundedQueen
study.Queen = GroundedQueen  # Explicit composition; no historical source file is changed.

ROOT = Path(__file__).resolve().parent
PHASES = {'C': list(range(3000, 3032)), 'D': list(range(4000, 4032))}


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()


def criteria(summary):
    s=summary['library']
    functional = {
        'every_trajectory_same_instance_and_state': s['state_retained']==s['trajectories'],
        'every_trajectory_three_revision_cycles': s['three_cycles']==s['trajectories'],
        'diagnosis_accuracy_at_least_95pct': s['correct_diagnoses']/s['audits'] >= 0.95,
        'live_success_at_least_90pct': s['task_correct']/s['task_calls'] >= 0.90,
        'future_success_at_least_99pct': s['future_correct']/s['future_checks'] >= 0.99,
        'zero_healthy_component_mispatch': s['healthy_component_mispatch']==0,
        'zero_future_regressions': s['future_regressions']==0,
    }
    attribution = {
        'true_origin_never_excluded': s['attribution_set_sound']==s['attribution_cases'],
        'every_symmetric_case_keeps_half_probability': s['symmetric_correct_uncertainty']==s['symmetric_cases'],
        'zero_incorrect_certainty': s['false_certain']==0,
        'identifiable_case_coverage_at_least_65pct': s['identified_when_identifiable']/s['full_view_identifiable'] >= 0.65,
        'all_decisions_match_inspected_evidence': s['attribution_read_consistent']==s['attribution_cases'],
    }
    return {'functional':functional,'attribution':attribution,
            'functional_pass':all(functional.values()),'attribution_pass':all(attribution.values()),
            'joint_pass':all(functional.values()) and all(attribution.values())}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=tuple(PHASES),required=True)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'docs/M37_FROZEN_SOURCES.json').read_text())
    actual={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in manifest['sha256']}
    if actual != manifest['sha256']:
        raise RuntimeError('frozen source mismatch; register a new protocol instead of continuing')
    suite=unittest.defaultTestLoader.loadTestsFromNames(['library_m33.tests','library_m37.tests'])
    result=unittest.TestResult(); suite.run(result)
    if not result.wasSuccessful() or result.skipped:
        raise RuntimeError('unit tests failed before validation')
    output=batch(PHASES[args.phase])
    output.update(phase=args.phase,python=platform.python_version(), tests_run=result.testsRun,
                  frozen_source_sha256=actual,pressure=pressure_cases())
    output['criteria']=criteria(output['summary'])
    data=encoded(output); digest=sha256(data).hexdigest()
    folder=ROOT/'results/m33_m36'; (folder/'runs').mkdir(parents=True,exist_ok=True)
    target=folder/'runs'/(digest+'.json.xz')
    if target.exists():
        if lzma.decompress(target.read_bytes())!=data:
            raise RuntimeError('archive collision')
    else:
        target.write_bytes(lzma.compress(data))
    summary={k:v for k,v in output.items() if k!='rows'}
    summary.update(archive=str(target.relative_to(ROOT)),raw_sha256=digest,
                   raw_bytes=len(data),compressed_bytes=target.stat().st_size)
    (folder/('phase_'+args.phase+'_summary.json')).write_bytes(encoded(summary))
    # All per-trajectory scientific observations remain inspectable without the full ledger.
    compact={'phase':args.phase,'raw_sha256':digest,'rows':[
        {**{k:v for k,v in row.items() if k!='trace'},
         'trace':{k:v for k,v in row['trace'].items() if k not in ('ledger','unresolved_epochs')}}
         for row in output['rows']]}
    (folder/('phase_'+args.phase+'_observations.json.xz')).write_bytes(lzma.compress(encoded(compact)))
    print(json.dumps({'phase':args.phase,'tests':result.testsRun,'criteria':output['criteria'],
                      'sha256':digest,'raw_bytes':len(data),'compressed_bytes':target.stat().st_size},indent=2))


if __name__=='__main__':
    main()
