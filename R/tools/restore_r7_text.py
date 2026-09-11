"""Restore the 25 full text records from Git chunks. Does not restore full run XZ.
No network or imports from the experiment. Reject paths outside R/results/r4_r7.
"""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import argparse
import json
import lzma

ROOT = Path(__file__).resolve().parents[1]


def require(value, message):
    if not value:
        raise ValueError(message)


def scoped(name, folder):
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and '.' not in p.parts,
            'unsafe relative path')
    path = ROOT.joinpath(*p.parts)
    base = ROOT.joinpath(*PurePosixPath(folder).parts).resolve()
    require(path.resolve().is_relative_to(base), 'outside allowed output folder')
    require(path.resolve() != base, 'file path required')
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='write after validating every record')
    args = ap.parse_args()
    metadata = json.loads((ROOT/'results/r4_r7/TEXT_MANIFEST.json').read_text())
    blocks = []
    for item in metadata['parts']:
        data = scoped(item['path'], 'results/r4_r7/text_parts').read_bytes()
        require(len(data) == item['bytes'] and sha256(data).hexdigest() == item['sha256'],
                'part mismatch: ' + item['path'])
        blocks.append(data)
    archive = b''.join(blocks)
    require(len(archive) == metadata['archive_bytes'] and
            sha256(archive).hexdigest() == metadata['archive_sha256'], 'archive mismatch')
    records = json.loads(lzma.decompress(archive).decode('utf-8'))
    require(isinstance(records, list) and len(records) == 25, 'unexpected record count')
    writes, names = [], set()
    for item in records:
        require(set(item) == {'path', 'content', 'sha256'}, 'unexpected record schema')
        require(item['path'] not in names, 'duplicate destination')
        names.add(item['path'])
        path = scoped(item['path'], 'results/r4_r7')
        require('runs' not in PurePosixPath(item['path']).parts,
                'text package is not full run data')
        data = item['content'].encode('utf-8')
        require(sha256(data).hexdigest() == item['sha256'], 'content checksum mismatch')
        if path.exists():
            require(path.is_file() and path.read_bytes() == data,
                    'refuse overwrite of different content: ' + item['path'])
        else:
            writes.append((path, data))
    if args.apply:
        for path, data in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
    print(json.dumps({'status': 'RESTORED' if args.apply else 'VALIDATED',
                      'records': len(records), 'new_files': len(writes),
                      'scope': 'full text evidence only; full A/B runs are in standalone package'}))


if __name__ == '__main__':
    main()
