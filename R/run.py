"""Run R experiment phases; every generated file stays inside this R directory."""
import argparse,hashlib,json,lzma,sys,platform
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
from src.study import batch

def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['dev','A','B']);args=ap.parse_args()
    seeds={'dev':[0,1],'A':list(range(5100,5108)),'B':list(range(6100,6108))}[args.phase]
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ['src','tests','vendor'] for p in sorted((ROOT/folder).rglob('*.py'))}
    manifest['run.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.phase!='dev':
        frozen=json.loads((ROOT/'FROZEN.json').read_text())
        if frozen['sources']!=manifest:raise RuntimeError('source changed after freeze')
    report=batch(seeds);report.update(phase=args.phase,python=platform.python_version(),source_sha256=manifest)
    report['verdict']=verdict(report)
    data=(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n').encode()
    sha=hashlib.sha256(data).hexdigest();folder=ROOT/'results';folder.mkdir(exist_ok=True)
    target=folder/(args.phase+'_'+sha+'.json.xz')
    target.write_bytes(lzma.compress(data))
    summary={k:v for k,v in report.items() if k not in ('episodes','stress')}
    summary.update(archive=target.name,raw_sha256=sha,compressed_bytes=target.stat().st_size)
    (folder/(args.phase+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

def verdict(report):
    c=report['summary']['evolve'];baseline=report['summary']['fixed_query'];N=len(report['seeds'])
    return {'functional_self_model':c['full_correct']==c['full_total'] and
          c['restored_correct']==c['full_correct'] and c['swapped_correct']/c['swapped_total']<.5 and
          c['removed_correct']/c['removed_total']<.5 and c['origin_symmetric_uncertain']==c['origin_cases'] and
          c['withdrawal_gated']==N and c['unrelated_self_preserved']==N,
        'bounded_meta_improvement':c['late_probes']/c['late_reviews']<=.75*baseline['late_probes']/baseline['late_reviews'] and
          c['online_correct']>=baseline['online_correct'],
        'strict_recursive_gate':all(e['strict_RSI_gate'] for e in report['episodes'] if e['method']=='evolve'),
        'phenomenal_consciousness':'NOT_ESTABLISHED; functional assays do not identify subjective experience'}

if __name__=='__main__':main()
