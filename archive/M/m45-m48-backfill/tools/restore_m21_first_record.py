"""无损恢复首轮记录与源码快照：只作明确JSON字段替换，不调用任务/学习器。"""
from pathlib import Path
from hashlib import sha256
import json,lzma
ROOT=Path(__file__).resolve().parents[1]

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()

def write_checked(path,raw,expected):
    if sha256(raw).hexdigest()!=expected:raise ValueError('restoration digest mismatch')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if lzma.decompress(path.read_bytes())!=raw:raise ValueError('existing archive differs')
    else:path.write_bytes(lzma.compress(raw,preset=6))

def main():
    folder=ROOT/'results/m21_m24'
    spec=json.loads((folder/'first_record_recipe.json').read_text())
    src=folder/'runs'/(spec['final_result_sha256']+'.json.xz')
    raw=lzma.decompress(src.read_bytes())
    if sha256(raw).hexdigest()!=spec['final_result_sha256']:raise ValueError('final archive digest mismatch')
    data=json.loads(raw)
    for patch in spec['replacements']:
        parent=data
        for key in patch['path'][:-1]:parent=parent[key]
        key=patch['path'][-1]
        if parent[key]!=patch['final']:raise ValueError('replacement precondition mismatch')
        parent[key]=patch['original']
    name=spec['first_result_sha256']
    write_checked(folder/'runs'/(name+'.json.xz'),encoded(data),name)
    sources={p:(ROOT/p).read_text() for p in spec['unchanged_source_paths']}
    sources.update({p:(ROOT/q).read_text() for p,q in spec['original_source_overrides'].items()})
    for p,text in sources.items():
        if sha256(text.encode()).hexdigest()!=data['source_sha256'][p]:raise ValueError('old source mismatch: '+p)
    name=spec['first_source_snapshot_sha256']
    write_checked(folder/'source_snapshots'/(name+'.json.xz'),encoded(sources),name)
    print('Restored and verified first record and source snapshot; no learner was run.')

if __name__=='__main__':main()
