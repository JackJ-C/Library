"""离线恢复补交的原始文字档案；默认检查，--apply 只新增，不覆盖任何文件。"""
from pathlib import Path, PurePosixPath
from hashlib import sha256
import argparse
import json
import lzma

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SHA256 = '933fa76125b3ceafc04c5164a734216dae95b86f28c73d3984e1ed5cdb588864'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='only create missing files')
    args = parser.parse_args()
    parts = ROOT / 'delivery/20260911/text_evidence.parts'
    packed = b''.join((parts / name).read_bytes() for name in ('000', '001'))
    if sha256(packed).hexdigest() != ARCHIVE_SHA256:
        raise ValueError('packed evidence hash mismatch')
    decoder = lzma.LZMADecompressor()
    data = decoder.decompress(packed, max_length=4_000_001)
    if len(data) > 4_000_000 or not decoder.eof or decoder.unused_data:
        raise ValueError('invalid or oversized evidence archive')
    archive = json.loads(data)
    if archive.get('format') != 'library-exact-utf8-files-v1':
        raise ValueError('unsupported format')
    paths, pending, matching = set(), [], []
    for item in archive['files']:
        path = PurePosixPath(item['path'])
        if path.is_absolute() or '..' in path.parts or '.git' in path.parts or not path.parts:
            raise ValueError('unsafe archive path')
        target = ROOT.joinpath(*path.parts)
        if not target.resolve().is_relative_to(ROOT.resolve()) or target.is_symlink():
            raise ValueError('path escapes repository or is a symlink')
        if str(path) in paths:
            raise ValueError('duplicate archive path')
        paths.add(str(path))
        content = item['content'].encode('utf-8')
        if sha256(content).hexdigest() != item['sha256']:
            raise ValueError('original file hash mismatch: ' + str(path))
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise ValueError('refusing to overwrite different file: ' + str(path))
            matching.append(str(path))
        else:
            pending.append((target, content))
    # Validate the entire archive before any writes. Existing mismatches abort unchanged.
    if args.apply:
        for target, content in pending:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(content)
    print(json.dumps({'status': 'RESTORED' if args.apply else 'CHECKED',
                      'files': len(paths), 'already_identical': len(matching),
                      'created' if args.apply else 'would_create': len(pending),
                      'archive_sha256': ARCHIVE_SHA256}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
