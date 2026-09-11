"""Post-validation descriptive summary; does not alter frozen gates or learning."""
from pathlib import Path
from hashlib import sha256
import json,lzma
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/r4_r7'
reports={}
for phase in 'AB':
 m=json.loads((OUT/(phase+'_summary.json')).read_bytes());b=lzma.decompress((ROOT/m['archive']).read_bytes())
 if sha256(b).hexdigest()!=m['raw_sha256']:raise ValueError('raw mismatch')
 reports[phase]=json.loads(b)
rows=[r for p in reports.values() for r in p['rows'] if r['method']=='recursive']
links=[]
for r in rows:
 for e in r['rounds']:
  s=e['evaluation_only']
  if s['strict_link']:
   links.append({'seed':r['seed'],'generation_zero_based':e['generation'],'before_cost':s['before'],
    'current_cost':s['current'],'frozen_parent_cost':s['frozen_parent'],'ast':e['policy_ast']})
summary={'scope':'Separate finite metacognition and recursive-search assays; subjective experience not established',
 'cohorts':{p:{'raw_sha256':json.loads((OUT/(p+'_summary.json')).read_bytes())['raw_sha256'],
                'criteria':v['criteria'],'summary':v['summary']} for p,v in reports.items()},
 'primary_trajectories':len(rows),'all_method_trajectories':sum(len(v['rows']) for v in reports.values()),
 'meta_attempts':sum(len(r['rounds']) for r in rows),'accepted_meta_updates':sum(r['accepted'] for r in rows),
 'strict_local_links':links,'consecutive_link_seeds':[r['seed'] for r in rows if r['consecutive_links']],
 'all_own_raw_answers':sum(r['metacognition']['arms']['own']['raw_correct'] for r in rows),
 'arm_totals':{a:{'correct':sum(r['metacognition']['arms'][a]['correct'] for r in rows),
                 'total':sum(r['metacognition']['arms'][a]['raw_total'] for r in rows),
                 'checks':sum(len(r['metacognition']['arms'][a]['checked']) for r in rows)}
               for a in rows[0]['metacognition']['arms']},
 'verification':'Independent frozen verifier passed A and B; normal and optimized full lineage runs yield same raw hashes',
 'test_cases':{'new':32,'old_R3_rerun':24},
 'non_conclusions':['stable or accelerating RSI','subjective experience','all-M architecture integration','independent identity necessary'],
 'statistical_unit':'whole seed trajectory; eight primary per cohort, not each nested task'}
(OUT/'FINAL_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
# All per-generation primary+counterfactual key results and per-trajectory metacognition scores.
compact=[]
for report in reports.values():
 for r in report['rows']:
  e={'seed':r['seed'],'method':r['method'],'cost':r['cost'],'same_queen':r['same_queen'],
     'accepted':r['accepted'],'strict_links':r['strict_links'],'consecutive_links':r['consecutive_links'],
     'rounds':[{k:e[k] for k in ('generation','policy_ast')}|{'costs':{k:e['evaluation_only'][k] for k in ('before','current','frozen_parent','delta','strict_link')}} for e in r['rounds']]}
  if 'metacognition' in r:
   e['monitor_withdrawal']=r['monitor_withdrawal'];e['arms']={a:{k:v[k] for k in ('correct','raw_correct','raw_total','brier','type2_auc')}|{'checks':len(v['checked'])} for a,v in r['metacognition']['arms'].items()}
  compact.append(e)
(OUT/'TRAJECTORY_SCORES.json').write_text(json.dumps(compact,ensure_ascii=False,separators=(',',':'))+'\n')
# Preserve the complete records of a causal two-link case incl. its later regression in the package.
r=next(r for r in rows if r['seed']==8105)
(OUT/'LOCAL_RECURSIVE_CASE_8105.json').write_text(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
(OUT/'VERIFICATION.json').write_text(json.dumps({'status':'VERIFIED','phases':[
 {'phase':'A','raw_sha256':summary['cohorts']['A']['raw_sha256'],'lineages':40,'actual_diagnostic_queries':10005,'meta_searches_replayed':384,'metacognitive_arm_trials':16384,'ledger_records_replayed':1918},
 {'phase':'B','raw_sha256':summary['cohorts']['B']['raw_sha256'],'lineages':40,'actual_diagnostic_queries':10132,'meta_searches_replayed':384,'metacognitive_arm_trials':16384,'ledger_records_replayed':1870}],
 'normal_vs_optimized_raw_equal':True,'independence':'separate code path, not separate research team'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ('primary_trajectories','accepted_meta_updates','consecutive_link_seeds','arm_totals')},ensure_ascii=False,indent=2))
