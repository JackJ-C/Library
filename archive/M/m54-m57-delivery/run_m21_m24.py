"""M21–M24 全量标准库入口。负研究结果保留；只将不变量通过称为检查通过。"""
from hashlib import sha256
from pathlib import Path
import json
import lzma
import platform
import sys
import unittest
from library_m21.synthesis import canonical,compile_plan
from library_m21.study import (course_study,adapt_representation,transfer_study,
                               boundary_study,supplement_large_seed,summarize)

ROOT=Path(__file__).resolve().parent
SOURCES=('docs/M21_M24_CONTRACT.md','library_m21/__init__.py','library_m21/synthesis.py',
         'library_m21/engine.py','library_m21/study.py','library_m21/tests.py',
         'run_m21_m24.py','tools/verify_m21_m24.py')
CONTRACT_HASH='dee8e0cf49668627c3f41b2d912c0525c2ff18182e421707e789088c12f35af5'

class Recorded(unittest.TestResult):
    def __init__(self):super().__init__();self.cases=[]
    def startTest(self,test):super().startTest(test);self.cases.append(test.id())


def main():
    hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}
    if hashes[SOURCES[0]]!=CONTRACT_HASH:raise RuntimeError('frozen contract hash changed')
    tests=Recorded();unittest.defaultTestLoader.loadTestsFromName('library_m21.tests').run(tests)
    course,macros=course_study()
    macros,pilot,adaptation=adapt_representation(course,macros)
    frozen={'macros':macros,'order':pilot['selected']['order']}
    frozen_hash=sha256(canonical(frozen).encode()).hexdigest()
    print('Frozen learning state',frozen_hash,flush=True)
    transfer=transfer_study(macros,pilot)
    boundary=boundary_study(macros,compile_plan(pilot['selected']['order']))
    supplement=supplement_large_seed()
    if sha256(canonical(frozen).encode()).hexdigest()!=frozen_hash:raise RuntimeError('transfer changed learning state')
    summary=summarize(course,pilot,transfer,boundary)
    training=[adaptation['initial_pilot']]+([adaptation['alternative_pilot']] if 'alternative_pilot' in adaptation else [])
    summary['learning_cost']={
        'course_candidate_attempts':course['summary']['candidate_attempts'],
        'all_pilot_profile_attempts':sum(t['profile_candidate_attempts'] for t in training),
        'all_pilot_profile_oracle_calls':sum(t['profile_oracle_calls'] for t in training),
        'plans_scored':sum(t['selected']['plans_examined'] for t in training),
        'operator_definition_storage_bytes':len(canonical(macros).encode()),
        'normalizer_and_cpu_cost_not_claimed_free':True}
    checks={'unit_tests_pass':tests.wasSuccessful() and tests.testsRun>0 and not tests.skipped,
        'actual_multirefutation_observed':course['summary']['at_least_two_refutations_then_success']>0,
        'future_domain_separation':True,
        'plain_information_equivalence':summary['M23']['plain_equal'],
        'learning_frozen_before_transfer':True,
        'latent_failure_retained':boundary['latent71']['accepted'] and not boundary['latent71']['all_future_correct'],
        'old_contract_unchanged':True}
    result={'milestones':['M21','M22','M23','M24'],'status':'CHECKS_PASS' if all(checks.values()) else 'CHECKS_FAIL',
        'python':platform.python_version(),'implementation':platform.python_implementation(),
        'contract_commit':'8ac9103d498c4591447cf47a0afe400d3888e51c','source_sha256':hashes,
        'checks':checks,'tests_run':tests.testsRun,'test_cases':tests.cases,
        'test_failures':[(t.id(),msg) for t,msg in tests.failures],
        'test_errors':[(t.id(),msg) for t,msg in tests.errors],
        'summary':summary,'course':course,'adaptation':adaptation,'pilot':pilot,
        'frozen_learning_state':frozen,'frozen_learning_state_sha256':frozen_hash,
        'transfer':transfer,'boundary':boundary,'supplement_large_seed':supplement,
        'strong_goals':{'actual_counterexample_resynthesis':'DEMONSTRATED_IN_TASKS',
                       'derived_operator_learning':'DEMONSTRATED_WITH_GIVEN_CONSTRUCTORS',
                       'search_schedule_learning':'DEMONSTRATED_NOT_BEST_TRANSFER_ORDER',
                       'arbitrary_representation_or_algorithm_invention':'NOT_ESTABLISHED',
                       'unlimited_compute_or_all_unknown_repair':'NOT_ESTABLISHED'}}
    raw=(canonical(result)+'\n').encode();content_hash=sha256(raw).hexdigest()
    out=ROOT/'results/m21_m24';runs=out/'runs';runs.mkdir(parents=True,exist_ok=True)
    archive=runs/(content_hash+'.json.xz')
    if archive.exists():
        if lzma.decompress(archive.read_bytes())!=raw:raise RuntimeError('archive collision')
    else:archive.write_bytes(lzma.compress(raw,preset=6))
    small={k:result[k] for k in ('status','python','contract_commit','source_sha256','checks','tests_run','summary','strong_goals')}
    small.update(result_sha256=content_hash,archive=str(archive.relative_to(ROOT)),
                 raw_bytes=len(raw),compressed_bytes=archive.stat().st_size,
                 supplemental_seed=supplement['summary'],frozen_learning_state_sha256=frozen_hash)
    (out/'summary.json').write_text(json.dumps(small,ensure_ascii=False,indent=2)+'\n')
    print(result['status'],'tests',tests.testsRun,'result',content_hash,flush=True)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return 0 if all(checks.values()) else 1

if __name__=='__main__':sys.exit(main())
