"""Operational R36 continuation after the tool's 45-second call timeout.
Not an algorithm revision: identical frozen episode, seeds, serialization and verifier.
Checks completed receipts before skipping them; never overwrites a trajectory archive.
"""
import argparse,gc,json,lzma,sys,time,traceback,hashlib
from pathlib import Path
from r32_r37.experiment import episode,METHODS,SEEDS
from .run_recovery import ROOT,check_sources,deny_external,now,canon,sha
from .verify_recovery import verify_file
from .sequence_metric import sequence_metric

def resume(batch,count):
    frozen=check_sources();sys.addaudithook(deny_external)
    out=ROOT/'results/r32_r37_recovery'/batch;out.mkdir(parents=True,exist_ok=True)
    audit=ROOT/'results/r32_r37_recovery/audit';audit.mkdir(parents=True,exist_ok=True)
    completed=0;ran=0
    for seed in SEEDS[batch]:
        for method in METHODS:
            path=out/f'{seed}_{method}.json.xz';receipt_path=out/f'{seed}_{method}.receipt.json';verify_path=audit/f'{seed}_{method}.verification.json'
            if path.exists():
                if not receipt_path.exists():raise RuntimeError('archive without receipt; preserve for explicit recovery: '+str(path))
                receipt=json.loads(receipt_path.read_bytes());raw=lzma.decompress(path.read_bytes())
                if receipt['recovery_frozen_sha256']!=frozen or sha(raw)!=receipt['raw_sha256'] or sha(path.read_bytes())!=receipt['xz_sha256']:
                    raise RuntimeError('existing archive integrity mismatch')
                if not verify_path.exists():verify_path.write_bytes(canon(verify_file(path)))
                completed+=1;del raw
                continue
            if ran>=count:continue
            stamp=now();t=time.perf_counter()
            try:
                r=episode(seed,method,method=='measured');raw=canon(r)
                with path.open('xb') as file:file.write(lzma.compress(raw,preset=3))
                receipt={'seed':seed,'method':method,'file':path.name,'started_utc':stamp,'finished_utc':now(),
                         'elapsed_seconds':time.perf_counter()-t,'raw_bytes':len(raw),'xz_bytes':path.stat().st_size,
                         'raw_sha256':sha(raw),'xz_sha256':sha(path.read_bytes()),'recovery_frozen_sha256':frozen,
                         'summary':r['summary'],'original_18_item_protocol_recovered':False,
                         'orchestration':'foreground chunk resume; original episode unchanged'}
                if method=='measured':
                    Q={(c,tuple(a)):(tuple(o),target) for c,a,o,target in r['closure']['quotient']}
                    metric=sequence_metric(Q);(audit/f'{seed}_sequence_metric.json').write_bytes(canon(metric))
                    receipt['supplemental_sequence_metric_sha256']=sha(canon(metric))
                receipt_path.write_bytes(canon(receipt));del r,raw;gc.collect()
                verify_path.write_bytes(canon(verify_file(path)));ran+=1;completed+=1
                print(json.dumps({'batch':batch,'seed':seed,'method':method,'verified':True,'elapsed':round(time.perf_counter()-t,3),'summary':receipt['summary']},ensure_ascii=False),flush=True)
            except Exception:
                (audit/f'{seed}_{method}.FAILURE.json').write_bytes(canon({'seed':seed,'method':method,'started_utc':stamp,'failed_utc':now(),'traceback':traceback.format_exc()}));raise
    check_sources();print('COMPLETED',batch,completed,'NEW',ran,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',choices=SEEDS);p.add_argument('--count',type=int,default=6);a=p.parse_args()
    if not 1<=a.count<=192:raise SystemExit('count out of scope')
    resume(a.batch,a.count)
