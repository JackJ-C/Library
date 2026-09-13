"""Read-only R31 publication tables. Primary A/B gates remain frozen."""
from collections import Counter
from hashlib import sha256
import json
import lzma
from pathlib import Path
from random import Random
from statistics import mean
import sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results'/'r28_r31'

def bootstrap(values):
    r=Random(20260913)
    s=sorted(mean(r.choices(values,k=len(values))) for _ in range(5000))
    return [s[125],s[4875]]

def main():
    public={'stage':'R28-R31','frozen_commit':'f7204df9c713b428e22b6106ef8d6569e3bc20aa',
        'disconnect_commit':'61e94edafb6f501b2a805d8e3e4ffb6409943083',
        'recovery_commit':'dc92fafd97e1de35240a28bed43d44f7b8a8a918',
        'batches':{},'scope':'finite offline intervention-response pseudometric; not open-ended RSI',
        'source_hash_checks':14,'frozen_tests_passed':35,'supplemental_tests_passed':12,
        'formal_trajectories':48,'space_trajectories':16,'generations_each':6,
        'complete_plain_reexecutions_equal':16,'extra_independent_samples_from_reexecution':0,
        'distribution_certificate':'UNKNOWN','conscious_experience':'not measured or excluded'}
    manifest=['batch\tfile\txz_bytes\txz_sha256\traw_json_sha256']
    scores=['batch\tseed\tmode\tmean_test_loss\tupdates\tstrict_links\tadjacent\tregressions\tactual_queries\tactual_price']
    allcost=Counter(); maincost=Counter(); allverification=Counter(); events=[]; failure=[]
    for batch in ('A','B'):
        s=json.loads((BASE/batch/'SUMMARY.json').read_text())
        gains=[r['methods']['raw']['mean_test_loss']-r['methods']['space']['mean_test_loss'] for r in s['rows']]
        rec=[r['methods']['space']['mean_recursive_gain'] for r in s['rows']]
        fg=[r['methods']['frozen']['mean_test_loss']-r['methods']['space']['mean_test_loss'] for r in s['rows']]
        for key,values in [('geometry_gain_95_bootstrap',gains),('local_recursive_gain_95_bootstrap',rec),('frozen_gain_95_bootstrap',fg)]:
            assert s['conclusions'][key]==bootstrap(values)
        details=Counter(); bc=Counter(); mode_means={}
        for mode in ('space','raw','frozen'):
            mode_means[mode]=mean(r['methods'][mode]['mean_test_loss'] for r in s['rows'])
        for receipt in s['archives']:
            path=BASE/batch/receipt['file']; packed=path.read_bytes(); raw=lzma.decompress(packed)
            assert sha256(packed).hexdigest()==receipt['xz_sha256']
            assert sha256(raw).hexdigest()==receipt['raw_sha256']
            x=json.loads(raw); bodies=[json.loads(r['body']) for r in x['ledger']]
            for key in ('own_queries','own_query_price','intervention_and_test_checks','ledger_records'):
                allverification[key]+=receipt['verification'][key]
            allcost.update(x['actual_cost'])
            manifest.append('\t'.join(map(str,[batch,receipt['file'],len(packed),receipt['xz_sha256'],receipt['raw_sha256']])))
            z=x['summary']; scores.append('\t'.join(map(str,[batch,x['seed'],x['mode'],z['mean_test_loss'],z['updates'],z['strict_empirical_links'],z['adjacent_links'],z['regressions'],x['actual_cost']['actual_queries'],x['actual_cost']['paid_probe_cost']])))
            if x['mode']!='space':continue
            maincost.update(x['actual_cost']);bc.update(x['actual_cost'])
            for r in x['rounds']:
                p=bodies[r['proposal_record']]; ch=bodies[r['check_record']]
                details['rounds']+=1;details['split_events']+=len(r['space']['splits'])
                details['rounds_with_class_split']+=bool(r['space']['splits'])
                details['rounds_with_multiple_axes']+=r['space']['dimension']>1
                details['total_local_classes']+=r['space']['classes'];details['total_axes']+=r['space']['dimension']
                details['previous_generation_adopted']+=r['previous_adopted']
                details['consecutive_actual_adoptions']+=r['previous_adopted'] and r['adopted']
                key=p['branches']['primary']['candidate']['key']
                details['nonparent_proposals']+=key!=p['parent']['key']
                details['wrong_association_changed_proposals']+=r['wrong_association_changes_proposal']
                details['collapsed_changed_proposals']+=key!=p['branches']['collapsed']['candidate']['key']
                details['previous_changed_proposals']+=key!=p['branches']['previous']['candidate']['key']
                details['initial_changed_proposals']+=key!=p['branches']['initial']['candidate']['key']
                for stage in ('proposal_cost','adoption_cost','evaluator_cost'):
                    for k,v in r[stage].items():bc[stage+'.'+k]+=v
                if r['adopted']:
                    event={'batch':batch,'seed':x['seed'],'generation_zero_based':r['generation'],
                           'parent':p['parent'],'child':r['child'],'empirical_adoption_gain':ch['checks']['primary']['certificate']['empirical_gain'],
                           'test_delta':r['delta'],'gamma_previous':r['gamma_previous'],'gamma_initial':r['gamma_initial'],
                           'previous_adopted':r['previous_adopted'],'test_means':r['evaluation_only']['means']}
                    events.append(event)
                    if r['delta']< -1e-12 or (r['previous_adopted'] and r['gamma_initial']<0):failure.append(event)
                    details['adopted_test_better']+=r['delta']>1e-12
                    details['adopted_test_worse']+=r['delta']< -1e-12
                    details['adopted_test_tied']+=abs(r['delta'])<=1e-12
        public['batches'][batch]={'seeds':s['seeds'],'primary':s['conclusions'],'method_mean_test_loss':mode_means,
                                 'posthoc_diagnostic_counts':dict(details),'space_route_costs_including_shared_shadows':dict(bc)}
    public['formal_arithmetic_checks']=dict(allverification)
    public['all_routes_actual_cost']=dict(allcost);public['space_routes_actual_cost']=dict(maincost)
    public['all_48_linkage_pass']=all(json.loads((BASE/f'SUPPLEMENTAL_AUDIT_{b}.json').read_text())['archive_count']==24 for b in 'AB')
    public['formal_source_unchanged']=True
    public['status']='EXPERIMENT_COMPLETED_WITH_NEGATIVE_RSI_AND_GEOMETRY_BENEFIT_RESULTS'
    for name,data in [('PUBLIC_SUMMARY.json',public),('ADOPTION_EVENTS.json',events),('FAILURE_EXAMPLES.json',failure)]:
        (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    (BASE/'ARCHIVE_MANIFEST.tsv').write_text('\n'.join(manifest)+'\n')
    (BASE/'TRAJECTORY_SCORES.tsv').write_text('\n'.join(scores)+'\n')
    print(json.dumps(public,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
