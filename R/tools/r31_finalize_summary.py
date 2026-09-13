"""Read-only reconstruction of formal batch summaries and matched ablations."""
from collections import Counter
import hashlib
import json
import lzma
from pathlib import Path
from random import Random
from statistics import mean
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from r28_r31.verify import equal


def bootstrap(values):
    rng=Random(20260913)
    samples=sorted(mean(rng.choices(values,k=len(values))) for _ in range(5000))
    return [samples[125],samples[4875]]


def main():
    root=ROOT/'results/r28_r31';facts={};raws=[]
    for batch,start in (('A',43100),('B',44100)):
        s=json.loads((root/batch/'SUMMARY.json').read_text());rows=[]
        assert s['seeds']==list(range(start,start+8))
        assert len(s['archives'])==24
        for seed in s['seeds']:
            methods={}
            for mode in ('space','raw','frozen'):
                p=root/batch/f'{seed}_{mode}.json.xz';xz=p.read_bytes();raw=lzma.decompress(xz)
                receipt=next(a for a in s['archives'] if a['file']==p.name)
                assert hashlib.sha256(xz).hexdigest()==receipt['xz_sha256']
                assert hashlib.sha256(raw).hexdigest()==receipt['raw_sha256']
                x=json.loads(raw);raws.append(x)
                methods[mode]={**x['summary'],'actual_cost':x['actual_cost'],'pressure':x['pressure']}
            rows.append({'seed':seed,'methods':methods})
        assert equal(rows,s['rows']),'formal rows disconnected from archives'
        primary=[r['methods']['space'] for r in rows]
        a=[r['methods']['raw']['mean_test_loss']-r['methods']['space']['mean_test_loss'] for r in rows]
        b=[r['methods']['space']['mean_recursive_gain'] for r in rows]
        c=[r['methods']['frozen']['mean_test_loss']-r['methods']['space']['mean_test_loss'] for r in rows]
        derived={'updates':sum(r['updates'] for r in primary),
                 'strict_empirical_links':sum(r['strict_empirical_links'] for r in primary),
                 'adjacent_link_trajectories':sum(r['adjacent_links'] for r in primary),
                 'regressions':sum(r['regressions'] for r in primary),
                 'changed_proposals':sum(r['changed_proposals'] for r in primary),
                 'mean_dimension':mean(r['mean_dimension'] for r in primary),
                 'mean_classes_of_eight':mean(r['mean_classes'] for r in primary),
                 'geometry_longitudinal_gain':mean(a),'geometry_gain_95_bootstrap':bootstrap(a),
                 'local_recursive_gain':mean(b),'local_recursive_gain_95_bootstrap':bootstrap(b),
                 'frozen_longitudinal_gain':mean(c),'frozen_gain_95_bootstrap':bootstrap(c),
                 'all_graph_reconstructions_identical':all(r['graph_identical'] for r in primary),
                 'all_revoke_checks_pass':all(all(r['pressure'][k] for k in ('entry_stopped','body_unchanged','reference_survives','recomputed_invalidity_matches')) for r in primary)}
        derived['geometry_benefit_gate']=derived['geometry_gain_95_bootstrap'][0]>0
        derived['finite_recursion_gate']=derived['adjacent_link_trajectories']>=4 and derived['local_recursive_gain_95_bootstrap'][0]>0 and derived['frozen_gain_95_bootstrap'][0]>0
        assert equal(derived,s['conclusions']),'formal conclusion or bootstrap not recomputable'
        facts[batch]={'frozen_conclusions':derived,'modes':{m:{
            'mean_test_loss':mean(r['methods'][m]['mean_test_loss'] for r in rows),
            'updates':sum(r['methods'][m]['updates'] for r in rows),
            'regressions':sum(r['methods'][m]['regressions'] for r in rows)} for m in ('space','raw','frozen')}}
    primary=[r for r in raws if r['mode']=='space'];rounds=[(r,x) for r in primary for x in r['rounds']]
    facts.update({'main_trajectory_count':len(primary),'all_trajectory_count':len(raws),
                  'main_actual_cost':dict(sum((Counter(r['actual_cost']) for r in primary),Counter())),
                  'all_actual_cost':dict(sum((Counter(r['actual_cost']) for r in raws),Counter())),
                  'main_all_engine_costs':{k:dict(sum((Counter(x[k]) for r,x in rounds),Counter())) for k in ('proposal_cost','adoption_cost','evaluator_cost')},
                  'posthoc_counts':json.loads((root/'POSTHOC_DIAGNOSTICS.json').read_text())['counts']})
    ablations={}
    for name in ('raw','collapsed','shuffled','previous','initial','graph'):
        c=Counter()
        for r,x in rounds:
            p=json.loads(r['ledger'][x['proposal_record']]['body'])
            c['changed_proposals']+=p['branches'][name]['candidate']['key']!=p['branches']['primary']['candidate']['key']
            child=p['branches'][name]['candidate']['key'] if x['checks'][name]['accepted'] else x['parent']['key']
            c['changed_successors']+=child!=x['child']['key']
            gain=x['evaluation_only']['means'][name]-x['evaluation_only']['means']['child']
            c['space_better']+=gain>1e-12;c['space_worse']+=gain < -1e-12;c['tie']+=abs(gain)<=1e-12
        ablations[name]=dict(c)
    (root/'REPLAY_SUMMARY.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2)+'\n')
    (root/'MATCHED_ABLATIONS.json').write_text(json.dumps({'scope':'96 matched rounds on 16 primary paths; not independent sustained routes','counts':ablations},indent=2)+'\n')
    print(json.dumps({'A_B_summary_reconstructed':True,'formal_archives':len(raws),'primary_rounds':len(rounds),'matched_ablations':ablations},indent=2))


if __name__=='__main__':main()
