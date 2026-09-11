"""Post-freeze execution orchestration only: same frozen lineage calls, checkpointed
at whole-lineage boundaries to fit the tool's execution time limit. No model,
threshold, seed, data filter or random stream changes. Not a background worker.
"""
from pathlib import Path
from hashlib import sha256
import argparse,json,lzma,platform,sys,io,unittest
from concurrent.futures import ProcessPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import run_r4_r7 as runner
from r4_r7.study import lineage,summarize,stress,METHODS

def compute_one(job):
    seed,method,path=job
    data=lineage(seed,method,True)
    target=Path(path);tmp=target.with_suffix('.tmp')
    tmp.write_bytes(lzma.compress(runner.enc(data)));tmp.replace(target)
    return seed,method


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('A','B'));ap.add_argument('part');args=ap.parse_args()
    frozen=json.loads((runner.OUT/'FROZEN.json').read_bytes())
    if runner.hashes()!=frozen['sources']:raise RuntimeError('source changed')
    if sha256((ROOT/'docs/R4_R7_CONTRACT.md').read_bytes()).hexdigest()!=frozen['contract_sha256']:raise RuntimeError('contract changed')
    cache=runner.OUT/('execution_parts_opt' if sys.flags.optimize else 'execution_parts')/args.phase;cache.mkdir(parents=True,exist_ok=True)
    if args.part=='all':
        jobs=[]
        for seed in runner.PHASES[args.phase]:
            for method in METHODS:
                p=cache/(str(seed)+'_'+method+'.json.xz')
                if p.exists():
                    v=json.loads(lzma.decompress(p.read_bytes()))
                    if v['seed']!=seed or v['method']!=method:raise RuntimeError('cache mismatch')
                else:jobs.append((seed,method,str(p)))
        with ProcessPoolExecutor(max_workers=4) as pool:
            futures=[pool.submit(compute_one,j) for j in jobs]
            for future in as_completed(futures):print('saved',*future.result(),flush=True)
        return
    if args.part!='assemble':
        seed=int(args.part)
        if seed not in runner.PHASES[args.phase]:raise ValueError('seed outside frozen cohort')
        for method in METHODS:
            path=cache/(str(seed)+'_'+method+'.json.xz')
            if path.exists():
                obj=json.loads(lzma.decompress(path.read_bytes()))
                if obj['seed']!=seed or obj['method']!=method:raise RuntimeError('wrong cache')
                print('already saved',seed,method,flush=True);continue
            data=lineage(seed,method,True)
            path.write_bytes(lzma.compress(runner.enc(data)))
            print('saved',seed,method,flush=True)
        return
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromName('r4_r7.tests')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (runner.OUT/(args.phase+'_tests.log')).write_text(stream.getvalue())
    if not result.wasSuccessful():raise RuntimeError(stream.getvalue())
    rows=[]
    for seed in runner.PHASES[args.phase]:
        for method in METHODS:
            p=cache/(str(seed)+'_'+method+'.json.xz')
            rows.append(json.loads(lzma.decompress(p.read_bytes())))
    summary=summarize(rows);press=stress()
    report={'phase':args.phase,'seeds':runner.PHASES[args.phase],'python':platform.python_version(),'sources':runner.hashes(),
            'tests':result.testsRun,'criteria':runner.gates(rows,summary,press),'summary':summary,'pressure':press,
            'rows':rows,'record_scope':'All recorded candidates, paid probes, forecasts and scores; full ledger for first primary lineage only'}
    report['problem_catalog']=runner.compact(rows,report['seeds'][0])
    data=runner.enc(report);h=sha256(data).hexdigest();out=runner.OUT/'runs';out.mkdir(exist_ok=True)
    path=out/(args.phase+'_'+h+'.json.xz')
    if not path.exists():path.write_bytes(lzma.compress(data,preset=9))
    elif lzma.decompress(path.read_bytes())!=data:raise RuntimeError('content collision')
    meta={k:v for k,v in report.items() if k not in ('rows','problem_catalog')}
    meta.update(archive=str(path.relative_to(ROOT)),raw_sha256=h,raw_bytes=len(data),compressed_bytes=path.stat().st_size)
    (runner.OUT/(args.phase+'_summary.json')).write_bytes(runner.enc(meta))
    print(json.dumps({'phase':args.phase,'sha256':h,'compressed':path.stat().st_size,'criteria':report['criteria']},indent=2))
if __name__=='__main__':main()
