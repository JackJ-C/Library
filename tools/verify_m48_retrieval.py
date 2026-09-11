"""Supplementary source/arithmetic verification, independent of the learning loop."""
from pathlib import Path
from hashlib import sha256
import json,lzma,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from verify_m45_m48 import check_task,independent_pairs,require


def verify(phase):
    folder=ROOT/'results/m45_m48'
    summary=json.loads((folder/f'retrieval_{phase}.json').read_text())
    raw=lzma.decompress((ROOT/summary['archive']).read_bytes());require(sha256(raw).hexdigest()==summary['sha256'],'supplement raw hash')
    data=json.loads(raw);f=json.loads((folder/'retrieval_freeze.json').read_text());require(data['freeze']==f,'supplement freeze')
    require(sha256((ROOT/'tools/m48_retrieval_audit.py').read_bytes()).hexdigest()==f['source_sha256'],'supplement source')
    require(sha256((ROOT/'docs/M48_RETRIEVAL_PROTOCOL.md').read_bytes()).hexdigest()==f['protocol_sha256'],'supplement contract')
    total=tasks=old_groups=0
    cohorts={}
    for row in data['rows']:
        cohorts.setdefault(row['seed'],{})[row['arm']]=row
        require(row['same_queen'] and row['historical_prefix_unchanged'],'continuity claim')
        require(row['incorrect_derived_cache']!=row['truth_evaluator_only'],'cache fault not real')
        for task in row['tasks']:check_task(task);tasks+=1
        records=row['ledger'];recovery=row['recovery'];models=None
        for group in recovery['groups']:
            commands=[];packet=None
            for k in group['evidence']:
                rec=records[k];body=json.loads(rec['body'])['data']
                if rec['kind']=='explore_intention':commands.append((body['object'],body['command']))
                else:packet=body['packet']
            pairs=independent_pairs(commands,packet);require(pairs==group['compatible_pairs'],'recovered pairs')
            permitted={tuple(m) for _,m in pairs};models=permitted if models is None else models & permitted
            if all(k<row['history_cut'] for k in group['evidence']):old_groups+=1
            require(row['revoked_key_evaluator_only'] not in group['evidence'],'withdrawn evidence reused')
        require(sorted(map(list,models))==recovery['models'],'derived cache supplanted raw evidence')
        if row['arm'] in ('library','plain','marginal'):
            require(bool(row['old_intention_reused']),'no old intention actually reused')
        if row['arm']=='withdraw_old_intention':require(not row['old_intention_reused'],'missing old group still used')
        total+=1
    for seed,arms in cohorts.items():
        a=arms['library'];b=arms['withdraw_old_intention']
        require(a['recovery']['cost']['probes']<b['recovery']['cost']['probes'],'no counterfactual probe difference')
        require(all(t['correct'] for e in arms.values() for t in e['tasks']),'supplement future failure')
        for m in ('plain','marginal'):
            require(a['recovery']['models']==arms[m]['recovery']['models'],'strong baseline mismatch')
    return {'phase':phase,'status':'VERIFIED','trajectories':total,'future_tasks_replayed':tasks,
            'genuinely_older_groups_replayed':old_groups,'sha256':summary['sha256']}

if __name__=='__main__':
    r=[verify(phase) for phase in ('C','D')]
    (ROOT/'results/m45_m48/retrieval_verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(r,ensure_ascii=False,indent=2))
