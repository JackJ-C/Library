"""Restore exact pre-validation M52 sources from the complete Git-stored XZ parts.
Offline, no execution of archive code. Refuses different existing files and unsafe paths.
"""
from pathlib import Path,PurePosixPath
from hashlib import sha256
import argparse,json,lzma
ROOT=Path(__file__).resolve().parents[1]
ALLOWED={'run_m52_confirm.py','tools/verify_m52.py','docs/M52_CONTRACT.md','results/m52/freeze.json'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    m=json.loads((ROOT/'delivery/m52/manifest.json').read_text());chunks=[]
    for part in m['parts']:
        p=ROOT/part['path']
        if not p.resolve().is_relative_to(ROOT.resolve()):raise ValueError('unsafe archive location')
        b=p.read_bytes()
        if sha256(b).hexdigest()!=part['sha256']:raise ValueError('part hash mismatch')
        chunks.append(b)
    archive=b''.join(chunks)
    if sha256(archive).hexdigest()!=m['compressed_sha256']:raise ValueError('archive hash mismatch')
    raw=lzma.decompress(archive)
    if sha256(raw).hexdigest()!=m['raw_sha256']:raise ValueError('raw source archive mismatch')
    entries=json.loads(raw)['files'];pending=[];seen=set()
    for e in entries:
        name=e['path'];pp=PurePosixPath(name)
        if pp.is_absolute() or '..' in pp.parts or name in seen:raise ValueError('unsafe/duplicate path')
        if not(name.startswith('library_m52/') or name in ALLOWED):raise ValueError('unapproved source path')
        seen.add(name);p=ROOT/name
        if not p.resolve().is_relative_to(ROOT.resolve()):raise ValueError('path leaves checkout')
        data=e['text'].encode()
        if sha256(data).hexdigest()!=e['sha256']:raise ValueError('source hash mismatch')
        if p.exists():
            if p.read_bytes()!=data:raise RuntimeError('refusing to overwrite different file: '+name)
        else:pending.append((p,data))
    if len(entries)!=m['source_files']:raise ValueError('source count mismatch')
    if args.apply:
        for p,data in pending:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    print(json.dumps({'verified_files':len(entries),'missing_before':len(pending),
                      'written':len(pending) if args.apply else 0,'raw_sha256':m['raw_sha256']}))
if __name__=='__main__':main()
