"""Offline restoration of the 38 original M57 text evidence files stored in Git.
Default: validate only. --apply: create missing files; never overwrite differing bytes.
"""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import argparse
import json
import lzma

ROOT = Path(__file__).resolve().parents[1]


def inside(name):
    part = PurePosixPath(name)
    if part.is_absolute() or '..' in part.parts or '\\' in name:
        raise ValueError('unsafe path: ' + name)
    path = ROOT / part
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('path leaves checkout: ' + name)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'delivery/m57/text_manifest.json').read_text())
    chunks = []
    for item in manifest['parts']:
        data = inside(item['path']).read_bytes()
        if len(data) != item['bytes'] or sha256(data).hexdigest() != item['sha256']:
            raise ValueError('part checksum mismatch: ' + item['path'])
        chunks.append(data)
    archive = b''.join(chunks)
    if sha256(archive).hexdigest() != manifest['compressed_sha256']:
        raise ValueError('compressed archive checksum mismatch')
    decoder = lzma.LZMADecompressor()
    raw = decoder.decompress(archive, max_length=manifest['raw_bytes'] + 1)
    if not decoder.eof or decoder.unused_data or len(raw) != manifest['raw_bytes']:
        raise ValueError('unexpected decompressed size or trailing archive data')
    if sha256(raw).hexdigest() != manifest['raw_sha256']:
        raise ValueError('text archive checksum mismatch')
    entries = json.loads(raw)['files']
    if len(entries) != manifest['files']:
        raise ValueError('file count mismatch')
    seen, pending = set(), []
    for item in entries:
        name = item['path']
        if name in seen or not (name == 'PACKAGE_MANIFEST.json' or
                               name.startswith(('audit/', 'results/m54_m57/'))):
            raise ValueError('duplicate or unapproved path: ' + name)
        seen.add(name)
        path = inside(name)
        data = item['text'].encode('utf-8')
        if sha256(data).hexdigest() != item['sha256']:
            raise ValueError('file checksum mismatch: ' + name)
        if path.exists():
            if not path.is_file() or path.read_bytes() != data:
                raise RuntimeError('refusing to overwrite different file: ' + name)
        else:
            pending.append((path, data))
    if args.apply:
        for path, data in pending:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
    print(json.dumps({'verified_files': len(entries),
                      'missing_before': len(pending),
                      'written': len(pending) if args.apply else 0,
                      'raw_sha256': manifest['raw_sha256'],
                      'large_raw_archives_included': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
