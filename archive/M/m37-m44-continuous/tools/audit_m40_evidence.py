"""冻结后只读补充审查：去掉评估器绝对位置，直接从事前作用切片重算归属。"""
from pathlib import Path
from hashlib import sha256
from collections import Counter
from random import Random
import json,lzma
ROOT=Path(__file__).resolve().parents[1]

def bootstrap(values):
    rng=Random(91137);n=len(values)
    means=sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(10000))
    return [means[249],means[9749]]

def check(flag,msg):
    if not flag:raise AssertionError(msg)

def run():
    phases=[];totals=Counter()
    for phase in ('A','B'):
        s=json.loads((ROOT/'results/m37_m40'/f'{phase}.json').read_text())
        data=lzma.decompress((ROOT/s['archive']).read_bytes())
        check(sha256(data).hexdigest()==s['sha256'],'raw archive')
        raw=json.loads(data);counts=Counter();episodes=[];method_cost={}
        for method in ('library','plain','recent','masked','no_revision','recalibrate'):
            splits={'live':Counter(),'future':Counter()};attr_reads=attr_comparisons=0
            for e in raw['batch']['episodes']:
                if e['method']!=method:continue
                for r in e['rows']:
                    for k,rs in (('live',[r['live']]),('future',r['future_execution'])):
                        for a in rs:
                            state='blocked' if not a['executed'] else ('correct' if a['after'][a['object']]==a['target'] else 'wrong')
                            splits[k][state]+=1
                for a in e['identity']:
                    attr_reads+=a['result']['budget']['reads'];attr_comparisons+=a['result']['budget']['comparisons']
            method_cost[method]={'execution_split':{k:dict(v) for k,v in splits.items()},'attribution_reads':attr_reads,
                                 'attribution_candidate_comparisons':attr_comparisons,
                                 'diagnostic_budget_cost':s['budget_cost'][method]}
        for e in raw['batch']['episodes']:
            if e['method']!='library':continue
            recs=e['slices'];reviews=[r for r in recs if r['kind']=='attribution_review']
            check(len(reviews)==len(e['identity']),'missing identity review')
            for a,r in zip(e['identity'],reviews):
                witness=recs[r['refs'][0]]; action=recs[witness['refs'][0]]
                check(action['kind']=='queen_action','not an actual issued action')
                check(action['seq']<witness['seq']<r['seq'],'causal order')
                issued=json.loads(action['body'])['data']['issued']
                public=a['result']['public_packet']
                # Does not use true_self_index, physical positions, actor label, ID or fingerprint.
                if not all('commands' in c for c in public):possible=[0,1]
                else:possible=[i for i,c in enumerate(public) if c['commands']==[issued]]
                check(bool(possible),'no history compatible with actual issued command')
                posterior=[1/len(possible) if i in possible else 0.0 for i in (0,1)]
                check(posterior==a['result']['probabilities'],'scores relied on privileged coordinates')
                counts['position_free_replays']+=1
                counts['identified' if len(possible)==1 else 'ambiguous']+=1
                if a['kind']=='changed':counts['actual_behavior_changed']+=1
            cycles=e['substantive_cycles']
            check(cycles[0]==0,'expected initialization separately recorded')
            counts['post_boot_revisions']+=len(cycles)-1
            counts['same_life_deliberate_error_then_rollback']+=all(e['post_episode_pressure'].values())
            c=e['counts'];episodes.append(c['future_correct']/c['future_tasks'])
        totals.update(counts)
        phases.append({'phase':phase,'counts':dict(counts),'future_trajectory_bootstrap_95pct':bootstrap(episodes),
                       'methods':method_cost,'independent_unit':'32 trajectory seeds, not task-level trials'})
    report={'status':'READ_ONLY_AUDIT_PASS','timing':'post-validation supplemental analysis; not used to select policies',
            'method':'Recompute attribution only from pre-action issued command and anonymous commands; endpoint-only views remain ambiguous',
            'remaining_assumptions':['trusted custody of the current controller own action log','exactly one true-own candidate',
                                     'equal prior for indistinguishable candidates','controlled synthetic alternative histories'],
            'world_truth_caveat':'Frozen study writes witnessed positions from the evaluator into intention_memory; all reported posteriors remain identical when these privileged position fields are removed. The frozen program is not altered.',
            'batches':phases,'totals':dict(totals)}
    p=ROOT/'results/m37_m40/supplemental_audit.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'totals':report['totals'],
                     'intervals':[(p['phase'],p['future_trajectory_bootstrap_95pct']) for p in phases]},ensure_ascii=False))
    return report
if __name__=='__main__':run()
