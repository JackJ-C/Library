"""检查原档、交付源码、逐次覆盖和逐输入四格统计；不代替重新执行。"""
from hashlib import sha256
from itertools import product
from pathlib import Path
import json
import lzma

ROOT=Path(__file__).resolve().parents[1]


def must(ok, reason):
    if not ok:raise ValueError(reason)


def main():
    summary=json.loads((ROOT/'results/m12_m15/summary.json').read_text())
    path=(ROOT/summary['archive']).resolve()
    must(path.is_relative_to(ROOT/'results/m12_m15/runs'),'archive outside allowed directory')
    raw=lzma.decompress(path.read_bytes())
    must(sha256(raw).hexdigest()==summary['result_sha256'],'result hash mismatch')
    data=json.loads(raw)
    for filename,digest in data['source_sha256'].items():
        must(sha256((ROOT/filename).read_bytes()).hexdigest()==digest,'source mismatch: '+filename)
    seen=set()
    for row in data['main']['rows']:
        key=(row['contract_age'],tuple(row['program']),tuple(row['sensor']),row['layout_seed'])
        must(key not in seen,'duplicate run');seen.add(key)
        mask=[row['program'][0]!=0,row['program'][1]!=row['contract_age'],row['program'][2]!=0]
        w=tuple(row['sensor'])!=(1,0)
        expected='both' if any(mask) and w else ('self' if any(mask) else ('worker' if w else 'healthy'))
        must(row['predicted_locus']==expected and row['qmask']==mask,'wrong localization')
        counts=[sum(bool(n&(1<<i)) for n in row['outcome_bitmasks']) for i in range(4)]
        must(counts==row['four_corner_correct_of_32'] and counts[3]==32,'outcome inconsistency')
        must(row['queen_changed']==any(mask) and row['worker_changed']==w,'wrong modification site')
    expected=set(product((0,1),product(range(2),range(2),range(3)),
                         product((-2,-1,1,2),(-7,0,5)),range(8)))
    must(seen==expected,'coverage incomplete')
    print(json.dumps({'verified':True,'runs':len(seen),'sha256':summary['result_sha256']},indent=2))


if __name__=='__main__':main()
