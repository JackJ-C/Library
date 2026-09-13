"""Result-fixed diagnostics of candidate supply and local response aliasing.

Not preregistered confirmatory tests. Exhaustive candidate test values are
computed only after all decisions and are never supplied to the learner.
No new trajectories or new experimental seeds are introduced.
"""
from collections import Counter
import json
import lzma
from pathlib import Path
from statistics import mean
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from r31_supplemental_audit import AuditEngine,fixture,INITIAL


def main():
    rows=[];total=Counter();cases=[]
    for path in sorted((ROOT/'results/r28_r31').glob('[AB]/*_space.json.xz')):
        x=json.loads(lzma.decompress(path.read_bytes()));bodies=[json.loads(r['body']) for r in x['ledger']]
        for r in x['rounds']:
            g=r['generation'];p=bodies[r['proposal_record']];pool=p['pool']
            tests=[fixture(x['seed']*100000+5000+g*20+j) for j in range(6)]
            e=AuditEngine(p['tasks'],tests)
            responses=[[e.run(b,j) for j in range(6)] for b in pool]
            testmeans=[mean(z['loss'] for z in row) for row in responses]
            signatures=[tuple(z['signature'] for z in row) for row in responses]
            requests=[tuple(z['requests'] for z in row) for row in responses]
            groups=r['space']['groups'];same_pairs=split_pairs=0
            for i in range(len(pool)):
                for j in range(i):
                    if groups[i]==groups[j]:
                        same_pairs+=1
                        split_pairs+=signatures[i]!=signatures[j]
            proposed=p['branches']['primary']['selection']['proposal']
            good=[i for i,v in enumerate(testmeans) if v<testmeans[0]-1e-12]
            gap=testmeans[0]-testmeans[proposed]
            choice_idx=next(i for i,b in enumerate(pool) if b['key']==r['child']['key'])
            row={'seed':x['seed'],'generation':g,'parent_test':testmeans[0],
                 'all_candidate_test_means':testmeans,'test_better_candidates':good,
                 'proposed_index':proposed,'proposed_test_gain':gap,'adopted':r['adopted'],
                 'actual_test_gain':r['delta'],'oracle_available_gain':testmeans[0]-min(testmeans),
                 'pilot_same_class_pairs':same_pairs,'those_pairs_split_on_test':split_pairs,
                 'observed_test_response_classes':len(set(signatures)),
                 'pilot_classes':r['space']['classes'],
                 'parent_noninitial':r['parent']['key']!=INITIAL['key'],
                 'parent_ast':r['parent']['ast'],'child_ast':r['child']['ast'],
                 'changed_outer_allocation_requests_on_test':requests[choice_idx]!=requests[0],
                 'gamma_previous':r['gamma_previous'],'gamma_initial':r['gamma_initial']}
            rows.append(row);total.update(e.cost)
            if r['adopted'] or gap>1e-12:
                cases.append({'seed':x['seed'],'generation':g,'parent':r['parent'],'child':r['child'],
                              'candidate':pool[proposed], 'adoption_bank_gain':r['checks']['primary']['certificate']['empirical_gain'],
                              'parent_test':testmeans[0],'proposal_test':testmeans[proposed],
                              'actual_test_gain':r['delta'],'gamma_previous':r['gamma_previous'],
                              'gamma_initial':r['gamma_initial'],'adopted':r['adopted']})
    counts={'rounds':len(rows),'rounds_with_test_better_available':sum(bool(r['test_better_candidates']) for r in rows),
            'rounds_proposing_test_better':sum(r['proposed_test_gain']>1e-12 for r in rows),
            'rejected_test_better_proposals':sum(r['proposed_test_gain']>1e-12 and not r['adopted'] for r in rows),
            'adopted_test_better':sum(r['adopted'] and r['actual_test_gain']>1e-12 for r in rows),
            'adopted_test_worse':sum(r['adopted'] and r['actual_test_gain']< -1e-12 for r in rows),
            'adopted_test_tie':sum(r['adopted'] and abs(r['actual_test_gain'])<=1e-12 for r in rows),
            'pilot_equal_pairs':sum(r['pilot_same_class_pairs'] for r in rows),
            'equal_pairs_split_on_test':sum(r['those_pairs_split_on_test'] for r in rows),
            'rounds_with_alias_split':sum(r['those_pairs_split_on_test']>0 for r in rows),
            'mean_pilot_classes':mean(r['pilot_classes'] for r in rows),
            'mean_test_response_classes':mean(r['observed_test_response_classes'] for r in rows),
            'rounds_noninitial_parent':sum(r['parent_noninitial'] for r in rows),
            'rounds_positive_gamma_previous':sum(r['gamma_previous']>1e-12 for r in rows),
            'rounds_positive_gamma_initial':sum(r['gamma_initial']>1e-12 for r in rows)}
    out={'label':'POST_HOC_DESCRIPTIVE_NOT_CONFIRMATORY','input':'already frozen space trajectories and their existing evaluator-only test bank',
         'oracle_warning':'test-best candidate is a retrospective upper reference, not available to Queen',
         'extra_simulated_cost':dict(total),'counts':counts,'cases':cases,'rows':rows}
    (ROOT/'results/r28_r31/POSTHOC_DIAGNOSTICS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(counts,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
