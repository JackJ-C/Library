"""M7 探索性目标审计；不把本审计用作 M3 的未见成绩。"""
from collections import Counter
from library_experiments import *
from run_m1_m6 import save_result


def main():
    rows, counts = [], Counter()
    for i, theta in enumerate(PARAMS):
        w = World(theta)
        d = diagnose(w.observe)
        u = d['choices'][0]
        old_nat = [w.execute(x, b) == b for x, b in CASES]
        w.apply(u)
        new_nat = [w.execute(x, b) == b for x, b in CASES]
        new_internal = [w.execute(x, b, neutral=True) == b for x, b in CASES]
        feasible = []
        for candidate in range(4):
            trial = World(theta)
            trial.apply(candidate)
            internal = [trial.execute(x, b, neutral=True) == b for x, b in CASES]
            natural = [trial.execute(x, b) == b for x, b in CASES]
            if all(internal) and all(not old or new for old, new in zip(old_nat, natural)):
                feasible.append(candidate)
        certified = common_safe(d['H'])
        require(certified == feasible, 'model certificate differs from independent execution')
        delta = sum(new_nat) - sum(old_nat)
        regress = sum(old and not new for old, new in zip(old_nat, new_nat))
        counts['internal_perfect'] += all(new_internal)
        counts['natural_mean_better'] += delta > 0
        counts['natural_mean_worse'] += delta < 0
        counts['natural_mean_unchanged'] += delta == 0
        counts['some_natural_case_regresses'] += regress > 0
        counts['no_feasible_correction'] += not feasible
        counts['certified_accept'] += bool(certified)
        counts['certified_nonzero_change'] += bool(certified) and certified != [0]
        counts['certificate_matches_exhaustion'] += certified == feasible
        rows.append([i, u, sum(old_nat), sum(new_nat), regress, feasible, certified])
    return save_result('m7', {'summary': {'worlds':256, **dict(counts)},
                            'columns':['world','correction','old_natural_successes','new_natural_successes','regressions','feasible','certified'],
                            'world_rows':rows, 'contract_commit':'92e3286e6e7cbc1cb4cfd17545bf31fdd856e054',
                            'command':'python3 run_m7.py'})

if __name__ == '__main__':
    main()
