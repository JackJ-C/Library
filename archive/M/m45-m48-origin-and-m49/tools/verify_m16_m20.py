"""读取内容寻址原档并核对源码和逐例覆盖。不会代替重跑实验。"""
from hashlib import sha256
from itertools import product
import json
import lzma
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from library_m16.synthesis import evaluate
from library_m16.study import INITIAL, VALIDATION, FUTURE, targets
from library_m16.recovery import SLOTS


def check(ok, why):
    if not ok:
        raise ValueError(why)


def main():
    summary = json.loads((ROOT / 'results/m16_m20/summary.json').read_text())
    path = (ROOT / summary['archive']).resolve()
    check(path.is_relative_to(ROOT / 'results/m16_m20/runs'), 'archive outside expected scope')
    raw = lzma.decompress(path.read_bytes())
    check(sha256(raw).hexdigest() == summary['result_sha256'], 'result hash mismatch')
    record = json.loads(raw)
    for name, expected in record['source_sha256'].items():
        p = (ROOT / name).resolve()
        check(p.is_relative_to(ROOT), 'source outside repo')
        check(sha256(p.read_bytes()).hexdigest() == expected, 'source changed: ' + name)
    check(record['status'] == 'CHECKS_PASS' and all(record['criteria'].values()), 'experiment not passed')
    check(not record['tests']['failures'] and not record['tests']['errors'] and not record['tests']['skipped'],
          'test failure hidden')
    check(len(record['tests']['passed']) == record['tests']['count'], 'test count mismatch')
    study = record['study']
    expected = set(product(('silent','exception'),range(4),range(1,64)))
    rows = study['M17']['rows']
    check({(r['mode'],r['damaged_cell'],r['fault_mask']) for r in rows} == expected
          and len(rows) == len(expected), 'M17 coverage missing/duplicated')
    for r in rows:
        required = {'cell-' + str(r['damaged_cell']) + ':' + s for i,s in enumerate(SLOTS)
                    if r['fault_mask'] & (1 << i)}
        changed = {c['subject'] + ':' + c['slot'] for c in r['changes']}
        check(changed == required and r['passed'] and r['future_correct'] == 172,
              'M17 incorrect row')
        check(r['instance_preserved'] and r['unaffected_bindings_preserved'], 'identity or write leakage')
    m18 = study['M18']
    functions = dict(targets())
    check(set(functions) == {r['task'] for r in m18['rows']} and len(m18['rows']) == 24,
          'M18 task coverage')
    for r in m18['rows']:
        check(r['accepted'] and r['future_x'] == list(FUTURE), 'M18 scope changed')
        values = [functions[r['task']](x) for x in FUTURE]
        # 树解释器与生成函数的实际结果、任务参考三方核对。
        check(values == r['future_expected'] == r['future_actual'] ==
              [evaluate(r['expression'],x) for x in FUTURE], 'M18 replay differs')
        check(all(x in INITIAL + VALIDATION for x, _ in r['query_trace']), 'heldout leaked into learning')
        check(r['oracle_calls'] == len(r['query_trace']), 'query count incorrect')
        check(r['plain_log_equal'] and r['history_comparison']['same_program'], 'control mismatch')
    check({(r['task'],r['damaged_cell']) for r in m18['integration']} ==
          set(product(functions,range(4))) and len(m18['integration']) == 96, 'integration coverage')
    check(all(r['passed'] and r['future_correct'] == 56 for r in m18['integration']), 'integration failure')
    m19 = study['M19']['summary']
    check(not m19['all_crashed_recovered'] and not m19['all_corrupt_recovered'], 'common failures lost')
    check(m19['latent_accepted'] and m19['latent_future_errors'] == [17], 'latent failure lost')
    check(m19['wrong_reference_future_errors'] == m19['tampered_installation_future_errors'] == 56,
          'trusted-boundary failures lost')
    check(all(v == 'NOT_ESTABLISHED' for v in record['strong_goals'].values()), 'scope overstated')
    print(json.dumps({'verified': True, 'result_sha256': summary['result_sha256'],
                      'unit_tests_recorded': record['tests']['count'],
                      'single_unit_cases': len(rows), 'program_tasks': len(m18['rows']),
                      'integration_cases': len(m18['integration']),
                      'note': '核对档案和独立表达式重放；不是重跑全部实验。'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
