"""Verify this delivery's byte manifest and formal raw/XZ receipts, read-only."""
from pathlib import Path
import hashlib
import json
import lzma
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    manifest=json.loads((ROOT/'results/r28_r31/DELIVERY_MANIFEST.json').read_text())
    for row in manifest['files']:
        p=ROOT/row['path']
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('delivery byte mismatch: '+row['path'])
    n=0
    for batch in ('A','B'):
        summary=json.loads((ROOT/'results/r28_r31'/batch/'SUMMARY.json').read_text())
        for row in summary['archives']:
            p=ROOT/'results/r28_r31'/batch/row['file'];xz=p.read_bytes();raw=lzma.decompress(xz)
            assert hashlib.sha256(raw).hexdigest()==row['raw_sha256'],p
            assert hashlib.sha256(xz).hexdigest()==row['xz_sha256'],p
            assert len(xz)==row['bytes'],p
            n+=1
    assert n==48
    sys.path.insert(0,str(ROOT))
    from r28_r31.run import check_frozen
    check_frozen()
    print(json.dumps({'manifest_files':len(manifest['files']),'formal_archives':n,
                      'frozen_sources':14,'all_match':True,'meaning':'integrity, not new scientific observations'}))

if __name__=='__main__':main()
