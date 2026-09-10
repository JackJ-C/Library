"""独立档案核验：不调用 Queen、学习器、世界生成器或训练入口。"""
from pathlib import Path
from hashlib import sha256
from collections import Counter
import argparse,json,lzma,sys

ROOT=Path(__file__).resolve().parents[1]


def require(ok,message):
    if not ok:raise AssertionError(message)


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def action_score(row):
    before,after=row['before'],row['after']
    if not row['executed']:
        require(before==after,'blocked task changed world')
        require(row['action'] is None,'blocked task has a command')
        return False
    obj=row['object'];other='teacup' if obj=='apple' else 'apple'
    require((after[obj]-before[obj])%5 == row['gain']*row['action']%5,'physical action mismatch')
    require(after[other]==before[other],'undeclared cross-object effect')
    return after[obj]==row['target']


def inspect_identity(row):
    public=row['result']['public_packet'];prob=row['result']['probabilities']
    require(all(set(p)<={'commands'} for p in public),'identity metadata or privileged coordinates leaked')
    truth=row['true_self_index'];other=row['other_execution']
    ambiguous=row['kind'] in ('identical','merge')
    if ambiguous:
        require(public[0]==public[1],'claimed unidentifiable pair differs')
        require(prob==[.5,.5],'false certainty in identical observations')
    elif row['result']['witness_used']:
        cmd=other['self_actual_command']
        possible=[i for i,p in enumerate(public) if p.get('commands')==[cmd]]
        require(possible==[truth],'identifiable transcript has wrong truth')
        require(prob[truth]==1,'recorded inference mismatches efference')
    else:require(prob==[.5,.5],'missing witness was guessed')
    require(row['equivariant'],'anonymous permutation fails')
    if row['kind']=='changed':
        require(other['self_actual_command']!=other['other_executed_commands'][0],
                'behavior-change test did not change behavior')
    require(abs(row['binary_brier']-(prob[0]-int(truth==0))**2)<1e-12,'bad Brier')


def inspect_slices(records):
    invalid=set();revoked=set();prefix=0;views=0;reviews=0
    for i,r in enumerate(records):
        require(r['seq']==i,'noncontiguous slice')
        for k in ('refs','deps'):require(all(0<=j<i for j in r[k]),'future/illegal edge')
        b=json.loads(r['body'])
        if r['kind']=='revocation':
            root=b['root'];revoked.add(root)
            # Recompute only on the known prefix; historical refs are not proof dependencies.
            invalid=set(revoked)
            for earlier in records[:i]:
                if any(p in invalid for p in earlier['deps']):invalid.add(earlier['seq'])
            require(set(b['invalidated'])<=invalid,'invalid revocation')
        if r['kind']=='intention_memory':
            action=records[r['refs'][0]]
            require(action['kind']=='queen_action','intent lacks actual action')
            issued=json.loads(action['body'])['data']['issued']
            require(b['data']=={'commands':[issued]},'privileged intention data entered new path')
        if r['kind']=='worker_view':
            require(set(('raw_seen','decoded','relations'))<=set(b['data']),'incomplete spatial slice')
            views+=1
        if r['kind']=='queen_action':
            require(set(('frame','issued','target','assumed_gain'))<=set(b['data']),'missing own-action evidence')
        if r['kind']=='review':reviews+=1
        prefix+=1
    return {'records':prefix,'worker_views':views,'reviews':reviews}


def verify_phase(name):
    summary=json.loads((ROOT/'results/m41_m44'/f'{name}.json').read_text())
    p=ROOT/summary['archive'];data=lzma.decompress(p.read_bytes())
    require(sha256(data).hexdigest()==summary['sha256'],'archive hash')
    report=json.loads(data)
    frozen=json.loads((ROOT/'results/m41_m44/freeze.json').read_text())
    require(report['source_sha256']==frozen['sources'],'tested/frozen source manifest')
    for path,h in frozen['sources'].items():require(sha256((ROOT/path).read_bytes()).hexdigest()==h,'source changed: '+path)
    require(sha256((ROOT/'docs/M41_M44_CONTRACT.md').read_bytes()).hexdigest()==frozen['contract_sha256'],'contract changed')
    require(report['batch']['seeds']==frozen[name+'_seeds'],'validation cohort changed')
    episodes=report['batch']['episodes'];cohorts={};action_count=0;identity_count=0;slice_count=0
    for e in episodes:
        cohorts.setdefault(e['seed'],{})[e['method']]=e
        live=future=post=post_n=0
        for r in e['rows']:
            good=action_score(r['live']);require(good==r['live_correct'],'live score mismatch');live+=good;action_count+=1
            checks=[action_score(v) for v in r['future_execution']]
            require(checks==r['future'],'future score mismatch');future+=sum(checks);action_count+=len(checks)
            if r['audit'] and r['audit']['status']=='accepted':
                post+=sum(checks);post_n+=len(checks)
                require(set(r['audit']['patches'])==set(r['before_expected_patch']),'patch target mismatch')
                require(r['audit']['actual_judge_binding_changed']==('queen_judge' in r['audit']['patches']),
                        'claimed judge change not bound')
            if r['audit']:
                b=r['audit']['budget']
                require(b['reads']<=24 and b['probes']<=6 and b['comparisons']<=6000,'budget exceeded')
        c=e['counts']
        require(live==c['live_correct'] and future==c['future_correct'],'episode totals')
        require(post==c.get('post_review_correct',0) and post_n==c.get('post_review_tasks',0),'post review totals')
        for ir in e['identity']:inspect_identity(ir);identity_count+=1
        if e['slices'] is not None:
            s=inspect_slices(e['slices']);slice_count+=s['records']
            require(e['counts']['same_queen'] and e['counts']['history_preserved'],'continuity not witnessed')
        if e['method'] in ('library','plain'):
            require(all(e['post_episode_pressure'].values()),'same-episode rollback/gate failure')
            require(e['post_episode_pressure'].get('withdrawn_support_closes_permission',False),'support retraction untested')
    for seed,m in cohorts.items():
        require(set(m)=={'library','plain','recent','masked','no_revision','recalibrate'},'missing control')
        ev=m['library']['events_evaluator_only']
        require(all(e['events_evaluator_only']==ev for e in m.values()),'method-dependent fault schedule')
        require(m['library']['counts']==m['plain']['counts'],'same-information log differs')
    require(len(cohorts)==32,'expected 32 independent episode seeds')
    return {'phase':name,'archive_sha256':summary['sha256'],'episodes':len(episodes),
            'executions_recomputed':action_count,'attributions_checked':identity_count,
            'slices_checked':slice_count,'joint_verdict_reported':report['verdict']['joint_pass']}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('C','D','both'),default='both',nargs='?')
    args=ap.parse_args();names=['C','D'] if args.phase=='both' else [args.phase]
    results=[verify_phase(n) for n in names]
    report={'status':'VERIFIED','phases':results,'independence':'separate code path, not separate research team'}
    p=ROOT/'results/m41_m44/verification.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False));return 0


if __name__=='__main__':sys.exit(main())
