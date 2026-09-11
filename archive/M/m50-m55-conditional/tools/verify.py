"""核对本轮实际归档和受测源码；不重写原档。"""
from hashlib import sha256
from pathlib import Path
import gzip
import json
import platform
import sys
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_m1_m7.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    archives = []
    for name in ('m1_m6', 'm7'):
        summary = json.loads((ROOT/'results'/(name+'_summary.json')).read_text())
        archive = ROOT/summary['archive']
        if archive.exists():
            raw = gzip.decompress(archive.read_bytes())
        else:
            # 仓库把本轮四份原记录打包；读取成员，不向外部路径解包。
            with tarfile.open(ROOT/'results/evidence_bundle.tar.xz', 'r:xz') as bundle:
                member = bundle.extractfile(summary['archive'][:-3])
                if member is None:
                    raise ValueError('missing evidence archive')
                raw = member.read()
        if sha256(raw).hexdigest() != summary['sha256_uncompressed']:
            raise ValueError('archive digest mismatch')
        record = json.loads(raw)
        for path, expected in record['source_sha256'].items():
            if sha256((ROOT/path).read_bytes()).hexdigest() != expected:
                raise ValueError('tested source mismatch: '+path)
        if record['summary'] != summary['summary']:
            raise ValueError('summary mismatch')
        archives.append(summary['sha256_uncompressed'])
    paths = [ROOT/n for n in ('library_experiments.py','run_m1_m6.py','run_m7.py','tests/test_m1_m7.py','tools/verify.py')]
    output = {'passed':result.wasSuccessful(), 'tests_run':result.testsRun,
              'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
              'python':platform.python_version(),'archives_verified':archives,
              'source_sha256':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths},
              'command':'python3 tools/verify.py'}
    (ROOT/'results'/'verification.json').write_text(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(main())
