"""Read-only reporting; not part of selection, thresholds, or frozen learner."""
from pathlib import Path
from collections import Counter
from random import Random
import json,lzma
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/m45_m48'


def interval(values):
    rng=Random(4548);n=len(values)
    a=sorted(sum(values[rng.randrange(n)] for _ in range(n))/n for _ in range(10000))
    return [a[249],a[9749]]


def main():
    combined={};primary=[];sources={}
    for phase in ('A','B'):
        s=json.loads((OUT/f'{phase}.json').read_text());raw=json.loads(lzma.decompress((ROOT/s['archive']).read_bytes()))
        sources[phase]=s['sha256']
        primary.extend(r for r in raw['batch']['rows'] if r['method']=='library')
        for m,c in s['summary'].items():combined.setdefault(m,Counter()).update(c)
    post=[v for r in primary for stage in r['stages'] if stage['learning'] for v in stage['future']]
    c=combined['library']
    ret={m:Counter() for m in ('library','plain','marginal','recent','withdraw_old_intention')}
    for phase in ('C','D'):
        s=json.loads((OUT/f'retrieval_{phase}.json').read_text());sources['retrieval_'+phase]=s['sha256']
        for arm,r in s['summary'].items():ret[arm].update(r)
    record={'scope':'M45-M48 locally completed; remote write not performed','raw_sha256':sources,
        'primary':dict(c),'all_controls':{m:dict(c) for m,c in combined.items()},
        'after_inference':{'correct':sum(v['correct'] for v in post),'tasks':len(post),
            'wrong_executions':sum(v['executed'] and not v['correct'] for v in post)},
        'all_natural_requests':{'correct':c['future_correct']+c['precheck_correct'],
            'tasks':c['future_tasks']+c['prechecks'],'excludes':'counterfactual arms and deliberate pressure tests'},
        'future_rate_trajectory_bootstrap_95':interval([r['counts']['future_correct']/r['counts']['future_tasks'] for r in primary]),
        'probe_reduction_relative_fixed':1-c['cost_probes']/combined['fixed_probe']['cost_probes'],
        'retrieval_confirmations':{m:dict(c) for m,c in ret.items()},
        'test_counts':{'new':23,'legacy_m37':34,'legacy_m41':12},
        'causal_caveat':'Cut removes efference-effect correspondence, not a pure verbal identity label. Counterfactual trials add bookkeeping to library/plain, making total scan cost unsuitable for direct cross-method runtime claims.'}
    (OUT/'FINAL_SUMMARY.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    first=primary[0]
    story={'seed':first['seed'],'stages':[s for s in first['stages'] if s['learning']],
           'gate':first['gate'],'failures':first['failures'],'source':'first primary A trajectory; no cherry-picking'}
    (OUT/'EXAMPLE_5000.json').write_text(json.dumps(story,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
