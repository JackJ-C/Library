"""复现M16–M20：有界交叉恢复和语法内程序合成，不是最终三项目标验收。"""
from hashlib import sha256
import json
import lzma
from pathlib import Path
import platform
import sys
import traceback
import unittest
from library_m16.synthesis import catalogue
from library_m16.study import run_all

ROOT = Path(__file__).resolve().parent
CONTRACT = 'docs/M16_M20_CONTRACT.md'
CONTRACT_HASH = 'e3fdf959b0a26cc0a7cbf295b77e68e11b56f6a6ca0c135dda0695c6fbea2f70'
CONTRACT_COMMIT = '88504a39c26254f62afeb3af76c290fc403cf875'
SOURCES = (CONTRACT, 'run_m16_m20.py', 'tools/verify_m16_m20.py',
           'library_m16/__init__.py', 'library_m16/synthesis.py',
           'library_m16/recovery.py', 'library_m16/study.py', 'library_m16/tests.py')


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


class RecordedResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.passed = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


def main():
    source_hashes = {s: sha256((ROOT / s).read_bytes()).hexdigest() for s in SOURCES}
    contract_ok = source_hashes[CONTRACT] == CONTRACT_HASH
    tests = RecordedResult()
    catalogue.cache_clear()
    unittest.defaultTestLoader.loadTestsFromName('library_m16.tests').run(tests)
    catalogue.cache_clear()
    data, study_error = {}, None
    try:
        data = run_all()
    except Exception:
        study_error = traceback.format_exc()
    criteria = {}
    if data:
        a, b, c = (data[m]['summary'] for m in ('M17','M18','M19'))
        criteria = {'all_504_single_unit_scenarios_recovered': a['cases'] == a['recovered'] == 504,
                    'normal_bindings_not_modified': a['mispatched_slots'] == 0 and a['normal_unchanged'],
                    '24_grammar_tasks_succeed': b['tasks'] == b['all_future_correct'] == 24,
                    '96_integrated_sequences_succeed': b['integration_cases'] == b['integration_passed'] == 96,
                    'same_information_controls_retained': b['plain_log_equal'] == b['remeasure_equal'] == 24,
                    'eight_context_failures_rejected': c['invalid_contexts_rejected'] == 8,
                    'common_cause_failures_retained': not c['all_crashed_recovered'] and not c['all_corrupt_recovered'],
                    'latent_failure_retained': c['latent_accepted'] and c['latent_future_errors'] == [17]}
    ok = (contract_ok and tests.testsRun > 0 and tests.wasSuccessful() and not tests.skipped
          and study_error is None and bool(criteria) and all(criteria.values()))
    record = {'milestones': ['M16','M17','M18','M19','M20'],
              'status': 'CHECKS_PASS' if ok else 'CHECKS_FAIL',
              'command': 'python3 run_m16_m20.py', 'python': platform.python_version(),
              'implementation': platform.python_implementation(),
              'contract_commit': CONTRACT_COMMIT, 'contract_hash_matches': contract_ok,
              'source_sha256': source_hashes, 'criteria': criteria,
              'tests': {'count': tests.testsRun, 'passed': tests.passed,
                        'failures': [[t.id(), tb] for t, tb in tests.failures],
                        'errors': [[t.id(), tb] for t, tb in tests.errors],
                        'skipped': [[t.id(), reason] for t, reason in tests.skipped]},
              'strong_goals': {'unconditional_whole_queen_audit': 'NOT_ESTABLISHED',
                               'arbitrary_unknown_mechanism_repair': 'NOT_ESTABLISHED',
                               'global_originality': 'NOT_ESTABLISHED'},
              'scope': 'known_single_unit_faults_and_bounded_grammar_synthesis',
              'study': data, 'study_error': study_error}
    raw = canonical(record)
    key = sha256(raw).hexdigest()
    output = ROOT / 'results' / 'm16_m20'
    runs = output / 'runs'
    runs.mkdir(parents=True, exist_ok=True)
    path = runs / (key + '.json.xz')
    if path.exists():
        if lzma.decompress(path.read_bytes()) != raw:
            raise RuntimeError('archive collision')
    else:
        path.write_bytes(lzma.compress(raw))
    summary = {k: record[k] for k in ('status','python','contract_commit','contract_hash_matches',
                                    'source_sha256','criteria','strong_goals','scope')}
    summary.update(result_sha256=key, archive=str(path.relative_to(ROOT)),
                   raw_bytes=len(raw), compressed_bytes=path.stat().st_size,
                   tests_run=tests.testsRun,
                   results={m: v['summary'] for m, v in data.items()})
    (output / 'summary.json').write_bytes(canonical(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
