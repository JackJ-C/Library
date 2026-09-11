"""Reconstruct complete M53/M54 sources from checked deltas over frozen M52.
Run restore_m52_sources.py --apply first. No archived program is executed.
"""
from pathlib import Path,PurePosixPath
from hashlib import sha256
import json,lzma,argparse
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE_SHA='851a34d2eed66aa688183a82939161bc0317a977b95bfde9d8a207d6417500da'

def safe(name):
    pp=PurePosixPath(name);p=ROOT/name
    if pp.is_absolute() or '..' in pp.parts or not p.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('unsafe source path')
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');a=ap.parse_args()
    b=(ROOT/'delivery/m53/source_delta.json.xz').read_bytes()
    if sha256(b).hexdigest()!=ARCHIVE_SHA:raise ValueError('source delta hash')
    entries=json.loads(lzma.decompress(b))['files'];pending=[];seen=set()
    for e in entries:
        name=e['path'];p=safe(name)
        if name in seen:raise ValueError('duplicate path')
        seen.add(name)
        if not(name.startswith('library_m53/') or name in ('run_m54_confirm.py','tools/verify_m54.py','docs/M53_M55_CONTRACT.md','results/m54/freeze.json')):
            raise ValueError('unapproved source path')
        if 'base' in e:
            old=safe(e['base']).read_text()
            if sha256(old.encode()).hexdigest()!=e['base_sha256']:raise ValueError('base source mismatch')
            edits=e['edits'];end=0
            for left,right,text in edits:
                if not 0<=end<=left<=right<=len(old):raise ValueError('overlapping edits')
                end=right
            new=old
            for left,right,text in reversed(edits):new=new[:left]+text+new[right:]
        else:new=e['text']
        data=new.encode()
        if sha256(data).hexdigest()!=e['sha256']:raise ValueError('restored source mismatch')
        if p.exists():
            if p.read_bytes()!=data:raise RuntimeError('refusing different existing file: '+name)
        else:pending.append((p,data))
    if a.apply:
        for p,data in pending:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    print(json.dumps({'verified':len(entries),'missing_before':len(pending),'written':len(pending) if a.apply else 0}))
if __name__=='__main__':main()
