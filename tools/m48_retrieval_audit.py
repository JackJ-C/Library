"""Separately frozen follow-on audit. Do not modify or reuse A/B as new confirmations."""
from pathlib import Path
from hashlib import sha256
from random import Random
from collections import Counter
import argparse,json,lzma,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from library_m45.study import make,task
from library_m45.core import MODELS,canonical

ARMS=('library','plain','marginal','recent','withdraw_old_intention')
SEEDS={'dev':list(range(4)), 'C':list(range(7000,7016)), 'D':list(range(8000,8016))}


def episode(seed,arm):
    method='library' if arm=='withdraw_old_intention' else arm
    q,w,port=make(seed,method);before_id,before_book=id(q),id(q.book)
    training=[]
    for phase in range(4):
        w.set_scene(phase,phase);q.activate(phase,phase);r=q.learn(port)
        checks=[task(q,w,o,d,Random(seed*73+phase*5+d),phase) for o in ('apple','teacup') for d in range(5)]
        training.append({'phase':phase,'learning':r,'tasks':checks})
    prefix=q.book.export();old_keys=[]
    for r in q.book.ledger.records:
        d=json.loads(r.body)['data']
        if r.kind=='explore_intention' and d['scene']==0:old_keys.append(r.seq)
    removed=None
    if arm=='withdraw_old_intention':
        removed=old_keys[0];q.book.revoke(removed,'external retraction of old efference; no replacement answer')
    # Evict only compiled policy; no restart, no fresh judge, no correct hidden model supplied.
    q.policies.pop(0,None);q.selected=None
    wrong_cache=next(m for m in MODELS if m!=w.contexts[0])
    q.last_control_model[0]=wrong_cache
    w.set_scene(0,4);q.activate(0,4)
    history_cut=len(q.book.ledger.records)
    r=q.learn(port)
    after=[task(q,w,o,d,Random(seed*19+d),4) for o in ('apple','teacup') for d in range(5)]
    old_replayed=[k for g in r['groups'] for k in g['evidence'] if k<history_cut]
    used_old_intention=[k for k in old_replayed if k in old_keys]
    return {'seed':seed,'arm':arm,'same_queen':id(q)==before_id and id(q.book)==before_book,
        'historical_prefix_unchanged':q.book.export()[:len(prefix)]==prefix,
        'prior_training':training,'old_intention_keys_evaluator_only':old_keys,
        'revoked_key_evaluator_only':removed,'history_cut':history_cut,
        'incorrect_derived_cache':list(wrong_cache),'recovery':r,
        'old_evidence_reused':old_replayed,'old_intention_reused':used_old_intention,
        'tasks':after,'truth_evaluator_only':list(w.permutation),
        'private_physics':port.private_log,'ledger':q.book.export()}


def frozen():
    return {'parent_freeze_sha256':sha256((ROOT/'results/m45_m48/freeze.json').read_bytes()).hexdigest(),
        'source_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
        'protocol_sha256':sha256((ROOT/'docs/M48_RETRIEVAL_PROTOCOL.md').read_bytes()).hexdigest(),
        'seeds':SEEDS,'registration':'local before new C/D; A/B not reclassified'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['dev','freeze','C','D']);a=ap.parse_args()
    out=ROOT/'results/m45_m48';f=out/'retrieval_freeze.json'
    if a.phase=='freeze':
        if f.exists():raise RuntimeError('already frozen')
        f.write_text(json.dumps(frozen(),sort_keys=True,indent=2)+'\n');print('FROZEN',sha256(f.read_bytes()).hexdigest());return
    if a.phase!='dev' and json.loads(f.read_text())!=frozen():raise RuntimeError('follow-on freeze drift')
    parent=json.loads((out/'freeze.json').read_text())
    for p,h in parent['sources'].items():
        if sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise RuntimeError('parent source changed')
    rows=[episode(s,arm) for s in SEEDS[a.phase] for arm in ARMS];summary={}
    for arm in ARMS:
        es=[r for r in rows if r['arm']==arm]
        summary[arm]={'episodes':len(es),'correct':sum(x['correct'] for e in es for x in e['tasks']),
            'tasks':sum(len(e['tasks']) for e in es),'probes':sum(e['recovery']['cost']['probes'] for e in es),
            'old_intention_reused':sum(bool(e['old_intention_reused']) for e in es),
            'old_group_reused':sum(bool(e['old_evidence_reused']) for e in es),
            'same_queen':sum(e['same_queen'] for e in es),'prefix_preserved':sum(e['historical_prefix_unchanged'] for e in es)}
    report={'phase':a.phase,'freeze':frozen(),'rows':rows,'summary':summary,
        'interpretation':'preserved raw history after evicting compiled controllers; stationary context; provided scene not provided witness'}
    data=(canonical(report)+'\n').encode();h=sha256(data).hexdigest();p=out/'runs'/(h+'.json.xz')
    if not p.exists():p.write_bytes(lzma.compress(data))
    report_summary={k:v for k,v in report.items() if k!='rows'}
    report_summary.update(archive=str(p.relative_to(ROOT)),sha256=h)
    (out/('retrieval_'+a.phase+'.json')).write_text(json.dumps(report_summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'phase':a.phase,'sha256':h,'summary':summary},ensure_ascii=False))

if __name__=='__main__':main()
