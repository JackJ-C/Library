"""Post-validation diagnostic, not a new selection policy or held-out success claim.
Uses the independent arithmetic interpreter; never changes the frozen runs.
"""
import json,lzma,sys
from pathlib import Path
from collections import Counter
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r20_r23_recovery.verify import Replay,eq,text
RESULTS=ROOT/'results/r20_r23_recovery'


def run(phase):
    summary=json.loads((RESULTS/f'{phase}_SUMMARY.json').read_text())
    counts=Counter();records=[];costs=Counter();live=Counter();verification=Counter()
    for receipt in summary['runs']:
        raw=lzma.decompress((ROOT/receipt['path']).read_bytes())
        if sha256(raw).hexdigest()!=receipt['sha256']:raise AssertionError('raw changed')
        r=json.loads(raw);flags=[];regressions=[]
        for z in r['rounds']:
            ev=z['evaluation_only'];p=z['primary'];g=z['generation']
            for name,entry in ev.items():
                if not eq(entry['mean'],sum(entry['parts'])/len(entry['parts'])):
                    raise AssertionError('mean not supported by replayed parts')
                verification['independently_checked_means']+=1
            child,parent,frozen=(ev[n]['mean'] for n in ('child','parent','frozen_child'))
            actual_change=text(p['after'])!=text(p['parent'])
            if actual_change!=z['allocator_rebound']:raise AssertionError('update count mismatch')
            link=g>0 and actual_change and child<parent-1e-12 and child<frozen-1e-12
            reg=child>parent+1e-12
            if link!=z['strict_link'] or reg!=z['regression']:raise AssertionError('link/regression mismatch')
            flags.append(link);regressions.append(reg)
            cases=[(t['problem'],t['target']) for t in r['heldout_evaluator_only']]
            replay=Replay(z['task_pool'],cases)
            oracle=[]
            for ast in p['pool']:
                parts=[replay.inner(ast,j,p['scale'])[0] for j in range(6)]
                oracle.append(sum(parts)/len(parts))
            best=min(oracle);headroom=best<parent-1e-12
            strict_headroom=g>0 and best<min(parent,frozen)-1e-12
            idx=p['outer']['chosen']
            seen_before={(a['arm'],a['repeat']) for a in p['nested']}
            shared_new=[i for i in (10,11,12) if (idx,i) in seen_before]
            shared_old=[i for i in (10,11,12) if (0,i) in seen_before]
            counts['rounds']+=1;counts['updates']+=actual_change
            counts['strict_links']+=link;counts['regressions']+=reg
            counts['pool_has_better_than_parent']+=headroom
            counts['pool_has_strict_counterfactual_headroom']+=strict_headroom
            counts['strict_headroom_missed']+=strict_headroom and not link
            counts['actual_child_tied_with_frozen']+=abs(child-frozen)<1e-12
            counts['actual_child_better_than_frozen']+=child<frozen-1e-12
            counts['actual_child_worse_than_frozen']+=child>frozen+1e-12
            counts['validation_split_reused_for_selected_arm']+=bool(shared_new)
            counts['validation_split_reused_for_parent_arm']+=bool(shared_old)
            counts['calibration_changes_selected_proposal']+=p['outer']['chosen']!=z['neutral_counter']['outer']['chosen']
            counts['calibration_changes_adopted_ast']+=text(p['after'])!=text(z['neutral_counter']['after'])
            counts['calibration_positive_transfer']+=ev['uncalibrated_child']['mean']>child+1e-12
            counts['calibration_negative_transfer']+=ev['uncalibrated_child']['mean']<child-1e-12
            for name in ('primary_cost','task_cost'):
                for k,v in z[name].items():costs[k]+=v
            records.append({'seed':r['seed'],'generation':g,'parent':p['parent'],'adopted':p['after'],
                'primary_loss':child,'parent_loss':parent,'frozen_child_loss':frozen,
                'uncalibrated_child_loss':ev['uncalibrated_child']['mean'],'oracle_minimum':best,
                'oracle_pool_means':oracle,'strict_link':link,'regression':reg,
                'strict_headroom':strict_headroom,'selected_check_split_overlap':shared_new,
                'parent_check_split_overlap':shared_old,'scale':p['scale']})
        if sum(flags)!=r['strict_links'] or sum(regressions)!=r['regressions']:raise AssertionError('summary miscounts')
        if sum(x['allocator_rebound'] for x in r['rounds'])!=r['updates']:raise AssertionError('wrong number updates')
        if any(a and b for a,b in zip(flags,flags[1:]))!=r['consecutive']:raise AssertionError('wrong consecutive flag')
        live.update(r['actual_diagnosis_cost']);counts['trajectories']+=1
        check=json.loads((RESULTS/f'{phase}_{r["seed"]}_normal_check.json').read_text())
        verification.update(check['independent_replay'])
    result={'phase':phase,'label':'POSTHOC_READ_ONLY_AUDIT_NOT_A_PROSPECTIVE_ORACLE_POLICY',
      'counts':dict(counts),'primary_meta_and_task_costs':dict(costs),'actual_diagnosis_cost':dict(live),
      'verification':dict(verification),'rounds':records,
      'limitation':'Pool oracle uses evaluation-only targets after validation. Its score is unattainable evidence of headroom, not agent performance. Check splits can overlap selection; no source or threshold changed.'}
    (RESULTS/f'{phase}_CANDIDATE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rounds'},ensure_ascii=False))

if __name__=='__main__':run(sys.argv[1])
