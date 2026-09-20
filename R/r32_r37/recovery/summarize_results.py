"""R37 descriptive analysis following pre-run PROTOCOL_RECOVERY.
Not imported by the learner; no result feeds back into experimental choices.
"""
from pathlib import Path
from collections import Counter,defaultdict
from statistics import mean
from random import Random
from itertools import product
import json,lzma,hashlib,csv

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/r32_r37_recovery'
METHODS=('legacy','measured','raw','frozen','certified','plain')
HIST_A={'legacy':(.08314646026234568,9,4,176),'measured':(.08382161458333333,8,4,0),'raw':(.08329113618827161,7,4,0),
        'frozen':(.08380353009259259,8,4,0),'certified':(.08321277006172839,10,6,0),'plain':(.08382161458333333,8,4,0)}

def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def load(p):return json.loads(lzma.decompress(p.read_bytes()))
def bootstrap(values,batch):
    rng=Random(20260920+(batch=='B'));x=sorted(mean(rng.choices(values,k=len(values))) for _ in range(5000))
    return [x[125],x[4875]]

def word_stream_check(r):
    """Independent expected stream digest from witnessed one-step cells, no simulator import."""
    T={(tuple(x['state']),tuple(x['action'])):tuple(x['next']) for x in r['closure']['rows']}
    O={(tuple(x['state']),tuple(x['action'])):list(x['output']) for x in r['closure']['rows']}
    Q={(c,tuple(a)):(tuple(o),t) for c,a,o,t in r['closure']['quotient']};G={tuple(s):g for s,g in r['closure']['groups']}
    h=hashlib.sha256();count=0;goal_checks=0
    for s in product(range(7),repeat=3):
        for a in product(range(2),range(7)):
            for b in product(range(2),range(7)):
                effects=[O[s,a],O[T[s,a],b]]
                h.update((canon([list(s),list(a),list(b),effects])+'\n').encode());count+=1
        for obj,goal in product(range(2),range(7)):
            direct=[a for a in range(7) if (s[obj]+O[s,(obj,a)][obj])%7==goal]
            quotient=[a for a in range(7) if (s[obj]+Q[G[s],(obj,a)][0][obj])%7==goal]
            if direct!=quotient:raise ValueError('same-information raw-table goal policy differs')
            goal_checks+=1
    expected=h.hexdigest();observed=r['sequence_evaluation_only']['actual_effect_stream_sha256']
    if expected!=observed:raise ValueError('complete length-two observed stream differs from evidence table')
    return {'seed':r['seed'],'word_stream_sha256':expected,'words':count,'same_information_goal_checks':goal_checks,'matched':True}

def main():
    allout={};tsv=[];counts=Counter();manifest=[];verification=[];wordchecks=[]
    for batch,first in (('A',73100),('B',74100)):
        receipts={};raws={};methodout={};detail=defaultdict(list);paired=Counter();shadow=defaultdict(Counter);atlas=Counter();adopt=Counter();certq=[]
        for seed in range(first,first+16):
            projected={}
            for method in METHODS:
                p=BASE/batch/f'{seed}_{method}.json.xz';recp=BASE/batch/f'{seed}_{method}.receipt.json'
                rec=json.loads(recp.read_bytes());r=load(p);receipts[seed,method]=rec;s=rec['summary']
                if r['summary']!=s:raise ValueError('receipt summary differs')
                audit=json.loads((BASE/'audit'/f'{seed}_{method}.verification.json').read_bytes())
                if not audit['valid'] or audit['raw_sha256']!=rec['raw_sha256']:raise ValueError('verification raw digest mismatch')
                counts['episodes']+=1;counts['generations']+=6;counts['raw_bytes']+=rec['raw_bytes'];counts['xz_bytes']+=rec['xz_bytes']
                counts['initial_cells_executed']+=s['closure_cells'];counts['recovery_cells_executed']+=r['pressure']['recovery_new_cells']
                counts['goal_moves']+=sum(x['spatial_step']['executed'] for x in r['rounds'])+r['pressure']['recovery_control']['executed']
                counts['all_pressure_pass']+=s['all_pressure_pass'];counts['controls_pass']+=s['all_controls_correct']
                detail[method].append(s)
                manifest.append({'path':str(p.relative_to(ROOT)),**{k:rec[k] for k in ('raw_sha256','xz_sha256','xz_bytes','raw_bytes')},'seed':seed,'method':method,'batch':batch})
                row={'batch':batch,'seed':seed,'method':method,**s};tsv.append(row)
                verification.append({'seed':seed,'method':method,'valid':True,'ledger_records':audit['ledger_records'],'closure_classes':audit['closure']['classes']})
                if method in ('measured','plain'):
                    projected[method]={'rounds':[{k:x[k] for k in ('parent','child','adopted','branches','evaluation_only','spatial_step')} for x in r['rounds']],
                                       'closure':r['closure'],'summary':s,'pressure':r['pressure']}
                if method=='certified':certq.extend(x['finite_certificate']['queries'] for x in r['rounds'])
                if method=='measured':
                    checked=word_stream_check(r);wordchecks.append(checked)
                    counts['sequence_words']+=r['sequence_evaluation_only']['words'];counts['sequence_transitions']+=r['sequence_evaluation_only']['transitions']
                    flags=[x['strict_empirical_link'] for x in r['rounds']];paired['strict_chain_trajectories']+=any(a and b for a,b in zip(flags,flags[1:]))
                    paired['any_strict_link_trajectories']+=any(flags)
                    for x in r['rounds']:
                        if x['atlas_previous_overlap']:atlas[x['atlas_previous_overlap']['status']]+=1
                        if x['adopted']:adopt['better' if x['delta']>1e-12 else 'worse' if x['delta'] < -1e-12 else 'tie']+=1
                        for name in ('graph','raw','collapsed','shuffled','previous','initial'):
                            shadow[name]['proposal_changed']+=x['branches'][name]!=x['branches']['primary']
                            gap=x['evaluation_only']['means'][name]-x['evaluation_only']['means']['child']
                            shadow[name]['measured_better' if gap>1e-12 else 'measured_worse' if gap < -1e-12 else 'equal']+=1
                    metrics=json.loads((BASE/'audit'/f'{seed}_sequence_metric.json').read_bytes())
                    counts['sequence_metrics_pass']+=metrics['fixed_point_and_ultrametric_checked'] and metrics['is_metric_on_quotient']
                del r
            paired['plain_semantic_matches']+=projected['measured']==projected['plain']
        for method,rows in detail.items():
            sums={k:sum(x[k] for x in rows) for k in ('updates','strict_links','regressions','metric_permutation_changes','proposal_permutation_changes','finite_exact_certificates','primary_model_interventions','primary_model_queries')}
            methodout[method]={'trajectories':len(rows),'mean_test_loss':mean(x['test_loss'] for x in rows),'mean_recursive_gain':mean(x['recursive_gain'] for x in rows),
                              'quotient_class_counts':dict(Counter(x['quotient_classes'] for x in rows)),
                              'all_controls_correct':all(x['all_controls_correct'] for x in rows),'all_pressure_pass':all(x['all_pressure_pass'] for x in rows),
                              'graph_equal_trajectories':sum(x['graph_candidate_equal'] for x in rows),**sums}
        contrasts={}
        for other in ('legacy','raw','frozen','certified','plain'):
            vals=[receipts[seed,other]['summary']['test_loss']-receipts[seed,'measured']['summary']['test_loss'] for seed in range(first,first+16)]
            contrasts[other]={'positive_means_measured_better':True,'mean':mean(vals),'descriptive_95_bootstrap':bootstrap(vals,batch),'paired_seed_differences':vals}
        recursive=[receipts[seed,'measured']['summary']['recursive_gain'] for seed in range(first,first+16)]
        H1=methodout['measured']['metric_permutation_changes']==methodout['measured']['proposal_permutation_changes']==0 and methodout['measured']['graph_equal_trajectories']==16 and paired['plain_semantic_matches']==16
        H2=all(x['all_controls_correct'] and x['all_pressure_pass'] for x in methodout.values())
        H5=all(contrasts[name]['mean']>0 and contrasts[name]['descriptive_95_bootstrap'][0]>0 for name in ('legacy','raw'))
        H6=paired['strict_chain_trajectories']>=8 and bootstrap(recursive,batch)[0]>0
        allout[batch]={'methods':methodout,'paired_contrasts':contrasts,'matched_shadow_diagnostics':dict(shadow),'measured_adoption_outcomes':dict(adopt),
                      'paired_checks':dict(paired),'atlas_overlap_status':dict(atlas),'certified_query_counts':{'sum':sum(certq),'min':min(certq),'max':max(certq)},
                      'recursive_gain_95_bootstrap':bootstrap(recursive,batch),'gates':{'H1_representation':H1,'H2_finite_closure_execution':H2,'H5_task_advantage':H5,'H6_stable_recursion':H6}}
    comp={}
    for method,(loss,updates,regressions,changes) in HIST_A.items():
        now=allout['A']['methods'][method]
        comp[method]={'mean_loss_abs_difference':abs(now['mean_test_loss']-loss),'updates_match':now['updates']==updates,'regressions_match':now['regressions']==regressions,
                      'permutation_changes_match':now['metric_permutation_changes']==changes,'aggregate_match':abs(now['mean_test_loss']-loss)<=1e-12 and now['updates']==updates and now['regressions']==regressions and now['metric_permutation_changes']==changes}
    result={'stage':'R37_RECOVERY_CLOSURE','scope':'conditional finite interventional response space; not open-world RSI or consciousness','batches':allout,'totals':dict(counts),
            'historical_A_comparison':comp,'old_A_raw_byte_identity':'NOT_TESTABLE_ORIGINAL_RAW_ARCHIVES_UNAVAILABLE','new_raw_archives':192,'old_18_file_freeze_complete':False,
            'source_code_changed':False,'independent_units':'16 paired seeds per batch, not 192 independent worlds or millions of independent words',
            'statistical_scope':'fixed synthetic mechanism family, descriptive small-sample bootstrap; no natural-world generalization claim'}
    (BASE/'PUBLIC_SUMMARY.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    (BASE/'ARCHIVE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (BASE/'VERIFICATION_SUMMARY.json').write_text(json.dumps(verification,indent=2)+'\n')
    (BASE/'SEQUENCE_STREAM_CHECKS.json').write_text(json.dumps(wordchecks,indent=2)+'\n')
    with (BASE/'TRAJECTORY_SCORES.tsv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(tsv[0]),delimiter='\t');writer.writeheader();writer.writerows(tsv)
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
