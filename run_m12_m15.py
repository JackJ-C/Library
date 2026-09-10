"""M12–M15 复现：完整原始 JSON 用标准 xz 压缩，不调用外部服务。"""
from hashlib import sha256
from pathlib import Path
import io
import json
import lzma
import platform
import sys
import traceback
import unittest
from library_m12.study import main_study, pressure_study

ROOT = Path(__file__).resolve().parent
CONTRACT_COMMIT = '5ed42557c1011afa11f14c078bd4b3adc36f7aa7'
CONTRACT_SHA256 = 'dd81a5c7e5ed5d7179864277e5fd675e5fa1f5c3e75426a685f1ff035041ff20'


class Recorded(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.names = []

    def startTest(self, test):
        self.names.append(test.id())
        super().startTest(test)


def main():
    files = sorted(list((ROOT/'library_m12').glob('*.py')) +
                   [ROOT/'run_m12_m15.py',ROOT/'docs/M12_M15_CONTRACT.md',ROOT/'library_m8/core.py'])
    manifest = {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files}
    if manifest['docs/M12_M15_CONTRACT.md'] != CONTRACT_SHA256:
        raise ValueError('frozen contract changed')
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Recorded).run(
        unittest.defaultTestLoader.loadTestsFromName('library_m12.tests'))
    report = {'milestones': ['M12','M13','M14','M15'], 'base_commit': '4a217bbd1236da6df989c7792d7b06f54da77e58',
              'contract_commit':CONTRACT_COMMIT, 'python':platform.python_version(),
              'command':'python3 run_m12_m15.py','source_sha256':manifest,
              'tests':{'run':tests.testsRun,'names':tests.names,'failures':len(tests.failures),
                       'errors':len(tests.errors),'skipped':len(tests.skipped)}, 'status':'FAIL'}
    try:
        report['main'] = main_study()
        report['pressure'] = pressure_study()
        s=report['main']['summary']
        okay=(s['runs']==2304 and s['correct_locus']==2304 and s['locality_pass']==2304
              and s['after_correct']==2304*32 and s['regressions']==0 and s['plain_equal']==2304)
        report['status']='PASS' if tests.wasSuccessful() and not tests.skipped and okay else 'FAIL'
    except Exception:
        report['exception']=traceback.format_exc()
    raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    digest=sha256(raw).hexdigest()
    output=ROOT/'results/m12_m15'
    runs=output/'runs'
    runs.mkdir(parents=True,exist_ok=True)
    archive=runs/(digest+'.json.xz')
    if archive.exists():
        if lzma.decompress(archive.read_bytes())!=raw:raise RuntimeError('archive conflict')
    else:archive.write_bytes(lzma.compress(raw))
    summary={k:v for k,v in report.items() if k not in ('main','pressure')}
    summary.update(result_sha256=digest,archive=str(archive.relative_to(ROOT)),
                   main_summary=report.get('main',{}).get('summary',{}),
                   by_locus=report.get('main',{}).get('by_locus',{}),
                   pressure=report.get('pressure',{}))
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    (output/'latest_tests.log').write_text(stream.getvalue())
    print(json.dumps({k:v for k,v in summary.items() if k not in ('pressure','source_sha256','tests')},
                     ensure_ascii=False,indent=2),flush=True)
    print('new unit tests:',tests.testsRun,'compressed bytes:',archive.stat().st_size,flush=True)
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
