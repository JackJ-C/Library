"""Offline frozen A/B runner. Run from R/: python -m r28_r31.run A."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
from random import Random
from statistics import mean
import sys

from .study import episode, MODES
from .verify import verify_episode

SEEDS = {'A': list(range(43100, 43108)), 'B': list(range(44100, 44108))}


def bootstrap(values, seed=20260913, repeats=5000):
    rng = Random(seed)
    values = list(values)
    samples = sorted(mean(rng.choices(values, k=len(values))) for _ in range(repeats))
    return [samples[int(.025 * repeats)], samples[int(.975 * repeats)]]


def check_frozen():
    root = Path(__file__).resolve().parents[1]
    frozen = json.loads((root / 'r28_r31' / 'FROZEN.json').read_text())
    for name, expected in frozen['sha256'].items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError('frozen source mismatch: ' + name)
    return root


def run(batch, output=None):
    root = check_frozen()
    output = Path(output) if output else root / 'results' / 'r28_r31' / batch
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    receipts = []
    for seed in SEEDS[batch]:
        methods = {}
        for mode in MODES:
            result = episode(seed, mode)
            verified = verify_episode(result)
            raw = (json.dumps(result, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':'), allow_nan=False) + '\n').encode()
            filename = str(seed) + '_' + mode + '.json.xz'
            path = output / filename
            if path.exists():
                raise FileExistsError('will not overwrite raw archive: ' + str(path))
            path.write_bytes(lzma.compress(raw))
            receipts.append({'file': filename, 'raw_sha256': hashlib.sha256(raw).hexdigest(),
                             'xz_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'bytes': path.stat().st_size, 'verification': verified})
            methods[mode] = {**result['summary'], 'actual_cost': result['actual_cost'],
                             'pressure': result['pressure']}
        rows.append({'seed': seed, 'methods': methods})
        print(batch, seed, json.dumps(methods['space'], ensure_ascii=False), flush=True)
    advantages = [r['methods']['raw']['mean_test_loss'] - r['methods']['space']['mean_test_loss'] for r in rows]
    recursion = [r['methods']['space']['mean_recursive_gain'] for r in rows]
    frozen_advantages = [r['methods']['frozen']['mean_test_loss'] - r['methods']['space']['mean_test_loss'] for r in rows]
    primary = [r['methods']['space'] for r in rows]
    conclusions = {
        'updates': sum(r['updates'] for r in primary),
        'strict_empirical_links': sum(r['strict_empirical_links'] for r in primary),
        'adjacent_link_trajectories': sum(r['adjacent_links'] for r in primary),
        'regressions': sum(r['regressions'] for r in primary),
        'changed_proposals': sum(r['changed_proposals'] for r in primary),
        'mean_dimension': mean(r['mean_dimension'] for r in primary),
        'mean_classes_of_eight': mean(r['mean_classes'] for r in primary),
        'geometry_longitudinal_gain': mean(advantages),
        'geometry_gain_95_bootstrap': bootstrap(advantages),
        'local_recursive_gain': mean(recursion),
        'local_recursive_gain_95_bootstrap': bootstrap(recursion),
        'frozen_longitudinal_gain': mean(frozen_advantages),
        'frozen_gain_95_bootstrap': bootstrap(frozen_advantages),
        'all_graph_reconstructions_identical': all(r['graph_identical'] for r in primary),
        'all_revoke_checks_pass': all(r['pressure']['entry_stopped'] and
                                     r['pressure']['body_unchanged'] and
                                     r['pressure']['reference_survives'] and
                                     r['pressure']['recomputed_invalidity_matches'] for r in primary),
    }
    conclusions['geometry_benefit_gate'] = conclusions['geometry_gain_95_bootstrap'][0] > 0
    conclusions['finite_recursion_gate'] = (
        conclusions['adjacent_link_trajectories'] >= 4 and
        conclusions['local_recursive_gain_95_bootstrap'][0] > 0 and
        conclusions['frozen_gain_95_bootstrap'][0] > 0)
    summary = {'batch': batch, 'seeds': SEEDS[batch], 'python': sys.version,
               'inference_unit': 'complete seed trajectory; bootstrap descriptive small-sample interval',
               'rows': rows, 'conclusions': conclusions, 'archives': receipts,
               'distribution_certified_rsi': False}
    (output / 'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('batch', choices=SEEDS)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = run(args.batch, args.output)
    print(json.dumps(result['conclusions'], indent=2, ensure_ascii=False))
