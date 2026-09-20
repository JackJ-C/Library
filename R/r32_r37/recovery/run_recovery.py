"""R36 recovery driver. Original 18-item run() is NOT changed or called.
Checks the 12 actually recovered original modules plus a separate recovery freeze,
then calls the original, byte-identical episode function. All raw results preserved.
"""
import argparse,hashlib,json,lzma,sys,time,gc,traceback
from datetime import datetime,timezone
from pathlib import Path
from r32_r37.experiment import episode,METHODS,SEEDS
from r32_r37.recovery.verify_recovery import verify_file
from r32_r37.recovery.sequence_metric import sequence_metric

ROOT=Path(__file__).resolve().parents[2]

def now():return datetime.now(timezone.utc).isoformat()
def canon(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def sha(data):return hashlib.sha256(data).hexdigest()

def check_sources():
    p=ROOT/'r32_r37/recovery/RECOVERY_FROZEN.json';f=json.loads(p.read_bytes())
    for path,h in f['sha256'].items():
        actual=sha((ROOT/path).read_bytes())
        if actual!=h:raise RuntimeError('recovery frozen source mismatch: '+path)
    original=json.loads((ROOT/'r32_r37/FROZEN.json').read_bytes())
    for path in f['verified_original_sources']:
        if sha((ROOT/path).read_bytes())!=original['sha256'][path]:raise RuntimeError('original frozen module mismatch: '+path)
    if tuple(METHODS)!=tuple(f['methods']) or SEEDS!=f['seeds']:raise RuntimeError('experiment identities changed')
    return sha(p.read_bytes())

def deny_external(event,args):
    if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.fork','os.posix_spawn'):
        raise RuntimeError('offline research guard: '+event)

def run(batch,start,end,verify=True):
    frozen=check_sources();sys.addaudithook(deny_external)
    out=ROOT/'results/r32_r37_recovery'/batch;out.mkdir(parents=True,exist_ok=True)
    audit=ROOT/'results/r32_r37_recovery/audit';audit.mkdir(parents=True,exist_ok=True)
    for seed in SEEDS[batch][start:end]:
        for method in METHODS:
            path=out/f'{seed}_{method}.json.xz'
            if path.exists():raise FileExistsError('preserving existing archive: '+str(path))
            stamp=now();t=time.perf_counter()
            try:
                result=episode(seed,method,method=='measured')
                raw=canon(result)
                with path.open('xb') as stream:stream.write(lzma.compress(raw,preset=3))
                receipt={'seed':seed,'method':method,'file':path.name,'started_utc':stamp,'finished_utc':now(),
                         'elapsed_seconds':time.perf_counter()-t,'raw_bytes':len(raw),'xz_bytes':path.stat().st_size,
                         'raw_sha256':sha(raw),'xz_sha256':sha(path.read_bytes()),'recovery_frozen_sha256':frozen,
                         'summary':result['summary'],'original_18_item_protocol_recovered':False}
                if method=='measured':
                    Q={(c,tuple(a)):(tuple(o),target) for c,a,o,target in result['closure']['quotient']}
                    metric=sequence_metric(Q)
                    (audit/f'{seed}_sequence_metric.json').write_bytes(canon(metric))
                    receipt['supplemental_sequence_metric_sha256']=sha(canon(metric))
                (out/f'{seed}_{method}.receipt.json').write_bytes(canon(receipt))
                del result,raw;gc.collect()
                if verify:
                    checked=verify_file(path)
                    (audit/f'{seed}_{method}.verification.json').write_bytes(canon(checked))
                print(json.dumps({'batch':batch,'seed':seed,'method':method,**receipt['summary']},ensure_ascii=False),flush=True)
            except Exception:
                failure={'seed':seed,'method':method,'started_utc':stamp,'failed_utc':now(),'traceback':traceback.format_exc()}
                (audit/f'{seed}_{method}.FAILURE.json').write_bytes(canon(failure))
                raise
    check_sources()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('batch',choices=('A','B'));p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int,default=16)
    a=p.parse_args()
    if not 0<=a.start<a.end<=16:raise SystemExit('start/end must bound an ordered nonempty seed interval in [0,16]')
    run(a.batch,a.start,a.end)
