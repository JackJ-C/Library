"""Independent arithmetic and evidence replay. Does not import Queen, World or study."""
from pathlib import Path
from hashlib import sha256
from itertools import permutations
from collections import Counter
import argparse,json,lzma
ROOT=Path(__file__).resolve().parents[1]
ALL=tuple((0,)+p for p in permutations(range(1,5)))


def require(v,why):
    if not v:raise AssertionError(why)


def check_task(r):
    b,a=r['before'],r['after'];obj=r['object'];other='teacup' if obj=='apple' else 'apple'
    if not r['executed']:
        require(b==a and r['command'] is None,'blocked execution moved state')
        require(not r['correct'],'blocked is not success');return False
    require(a[other]==b[other],'undeclared cross action')
    require(a[obj]==(b[obj]+r['map'][r['command']])%5,'physical output mismatch')
    right=a[obj]==r['goal'];require(right==r['correct'],'wrong scoring')
    return right


def independent_pairs(commands,packet):
    require(set(packet)=={'paths'} and len(packet['paths'])==3,'source leak or source number')
    found=[]
    for i,path in enumerate(packet['paths']):
        require(len(path)==len(commands),'unmatched observations')
        for frame in path:require(set(frame)=={'before','after'},'secret command/id/source in external packet')
        for model in ALL:
            agree=True
            for (obj,command),frame in zip(commands,path):
                for worker in (0,1):
                    delta=(frame['after'][worker][obj]-frame['before'][worker][obj])%5
                    other=1-obj
                    if delta!=model[command] or frame['after'][worker][other]!=frame['before'][worker][other]:agree=False
            if agree:found.append([i,list(model)])
    return found


def verify(name):
    folder=ROOT/'results/m45_m48';s=json.loads((folder/(name+'.json')).read_text())
    raw=lzma.decompress((ROOT/s['archive']).read_bytes());require(sha256(raw).hexdigest()==s['sha256'],'raw digest')
    report=json.loads(raw);freeze=json.loads((folder/'freeze.json').read_text())
    require(report['source_sha256']==freeze['sources'],'manifest drift')
    for path,h in freeze['sources'].items():require(sha256((ROOT/path).read_bytes()).hexdigest()==h,'source drift: '+path)
    require(sha256((ROOT/'docs/M45_M48_CONTRACT.md').read_bytes()).hexdigest()==freeze['contract_sha256'],'contract drift')
    rows=report['batch']['rows'];seeds=freeze['seeds'][name]
    require(len(rows)==len(seeds)*8,'paired cohort coverage')
    totals=Counter();seen={}
    for row in rows:
        seen[(row['seed'],row['method'])]=row
        correct=0
        require(len(row['stages'])==16,'continuity task windows')
        for stage in row['stages']:
            for t in stage['future']:correct+=check_task(t);totals['future_tasks']+=1
            if stage['precheck'] is not None:check_task(stage['precheck']);totals['prechecks']+=1
            if stage['causal']:
                arms=stage['causal']['arms']
                for v in arms.values():
                    for t in v:check_task(t);totals['causal_task_executions']+=1
                for f,c,r in zip(arms['factual'],arms['remove_source_constraints'],arms['restore']):
                    require(f['before']==c['before']==r['before'] and f['goal']==c['goal']==r['goal'],'unmatched intervention trials')
                    require(f['command']==r['command'] and f['correct']==r['correct'],'failed restoration')
                    require(c['executed']==(c['delta']==0),'weak prior yields only zero common command')
        require(correct==row['counts']['future_correct'],'row aggregate')
        for p in row['private_physics']:
            for round in p['rounds']:
                for r in round:
                    obj=('apple','teacup')[r['object']]
                    require(r['after'][obj]==(r['before'][obj]+r['map'][r['command']])%5,'non-actual competitor trajectory')
                    totals['exploration_actor_actions']+=1
        records=row['ledger']
        if records:
            by_interval={p['interval']:p for p in row['private_physics']}
            groups={}; invalid=set();children={};normal_permit=None
            for i,r in enumerate(records):
                require(r['seq']==i,'slice order')
                for k in r['refs']+r['deps']:require(0<=k<i,'nonhistorical edge')
                require(not any(k in invalid for k in r['deps']),'proof from invalid support')
                for k in r['deps']:children.setdefault(k,set()).add(i)
                body=json.loads(r['body']);d=body.get('data',body)
                if r['kind']=='revocation':
                    queue=[body['root']];changed=set()
                    while queue:
                        k=queue.pop()
                        if k in invalid:continue
                        invalid.add(k);changed.add(k);queue+=list(children.get(k,()))
                    require(changed==set(body['invalidated']),'wrong withdrawal closure')
                if r['kind']=='explore_intention':groups.setdefault(d['interval'],[]).append((d['object'],d['command']))
                if r['kind']=='anonymous_effects':
                    commands=groups[d['interval']];packet=d['packet']
                    private=by_interval[d['interval']];order=private['order']
                    require(len(commands)==len(packet['paths'][0]),'action not before outcome')
                    for anon,path in enumerate(packet['paths']):
                        actor=order[anon]
                        for j,frame in enumerate(path):
                            actual=private['rounds'][j][actor]
                            require(frame['before'][0]==[actual['before']['apple'],actual['before']['teacup']], 'public before fabricated')
                            require(frame['after'][0]==[actual['after']['apple'],actual['after']['teacup']], 'public after fabricated')
                    totals['anonymous_frames_replayed']+=len(commands)*3
                if r['kind']=='source_model_review':
                    result=d['result']
                    for group in result['groups']:
                        evidence=group['evidence'];cmd=[];packet=None
                        for key in evidence:
                            rec=records[key];bd=json.loads(rec['body'])['data']
                            if rec['kind']=='explore_intention':cmd.append((bd['object'],bd['command']))
                            else:packet=bd['packet']
                        pairs=independent_pairs(cmd,packet)
                        require(pairs==group['compatible_pairs'],'source-mechanism pairs not evidence based')
                        totals['joint_source_model_replays']+=1
                    models=result['models'];inverse=[]
                    for delta in range(5):
                        candidates={tuple(m).index(delta) for m in models}
                        inverse.append(next(iter(candidates)) if len(candidates)==1 else None)
                    require(inverse==result['inverse'],'non-unanimous approved command')
                if r['kind']=='control_permission':normal_permit=i
                if r['kind']=='controlled_intention':
                    require(len(r['deps'])==1 and r['deps'][0] not in invalid,'execution with withdrawn source evidence')
                totals['ledger_records_checked']+=1
        if row['gate']:require(all(row['gate'].values()),'gate result incomplete')
    for seed in seeds:
        primary=seen[(seed,'library')]
        for method in ('plain','marginal'):
            other=seen[(seed,method)]
            require([v['correct'] for s in primary['stages'] for v in s['future']]==
                    [v['correct'] for s in other['stages'] for v in s['future']], 'strong baseline mismatch')
    return {'phase':name,'status':'VERIFIED','sha256':s['sha256'],'trajectories':len(rows),**totals,
            'scope':'arithmetic/evidence/gating replay plus recorded instance assertions; not independent laboratory'}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['A','B','both'],default='both',nargs='?');a=ap.parse_args()
    result=[verify(n) for n in (['A','B'] if a.phase=='both' else [a.phase])]
    (ROOT/'results/m45_m48/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
