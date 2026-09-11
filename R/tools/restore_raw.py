"""Restore exact recorded JSON from a checked, lossless bundle; no code execution."""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import json
import lzma

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 32 * 1024 * 1024


def path_in_results(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != 'results':
        raise ValueError('archive path outside R/results')
    dest = ROOT.joinpath(*p.parts)
    if not dest.resolve().is_relative_to((ROOT / 'results').resolve()):
        raise ValueError('symlink outside R/results')
    return dest


def unpack(data):
    decoder = lzma.LZMADecompressor(memlimit=128*1024*1024)
    raw = decoder.decompress(data, max_length=LIMIT+1)
    if len(raw) > LIMIT or not decoder.eof or decoder.unused_data:
        raise ValueError('oversized or invalid single-stream archive')
    return raw


def main():
    spec = json.loads((ROOT/'results/RAW_MANIFEST.json').read_text())
    parts = []
    for p in spec['parts']:
        data = path_in_results(p['path']).read_bytes()
        if len(data) != p['bytes'] or sha256(data).hexdigest() != p['sha256']:
            raise ValueError('raw chunk hash mismatch')
        parts.append(data)
    payload = b''.join(parts)
    if len(payload) != spec['bytes'] or sha256(payload).hexdigest() != spec['sha256']:
        raise ValueError('bundle hash mismatch')
    contents = json.loads(unpack(payload))
    if contents['format'] != 'R-raw-v1':
        raise ValueError('unknown archive format')
    expected = {p['path']:p for p in spec['files']}
    rows = contents['files']
    if len(rows) != len(expected) or {r['path'] for r in rows} != set(expected):
        raise ValueError('missing, duplicate or extra raw records')
    pending = []
    for row in rows:
        raw = row['raw'].encode('utf-8')
        target = path_in_results(row['path'])
        m = expected[row['path']]
        if sha256(raw).hexdigest() != row['raw_sha256'] or row['raw_sha256'] != m['raw_sha256']:
            raise ValueError('raw JSON hash mismatch')
        if len(raw) != m['raw_bytes']:
            raise ValueError('raw size mismatch')
        if target.exists():
            if unpack(target.read_bytes()) != raw:
                raise ValueError('refusing to overwrite different evidence: '+row['path'])
        else:
            pending.append((target, lzma.compress(raw)))
    # Validate the entire bundle and all collisions before writing any output.
    for target, data in pending:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:
            f.write(data)
    print(json.dumps({'status':'RESTORED','raw_files':len(rows),'new_files':len(pending),
                      'identity':'SHA256 of exact uncompressed UTF-8 JSON'},ensure_ascii=False))


if __name__ == '__main__':
    main()
