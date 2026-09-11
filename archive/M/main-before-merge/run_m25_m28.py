"""M25–M28复现入口：冻结合同、执行测试、保留完整内容寻址记录。"""
from hashlib import sha256
import io
import json
import lzma
from pathlib import Path
import platform
import sys
import traceback
import unittest
from library_m25.language import canonical
from library_m25.experiments import study

ROOT=Path(__file__).resolve().parent
CONTRACT='98c4b0ecb9fff20794c049d0c584ec4dfcabba7b0188136a6561190059e596de'


class RecordedResult(unittest.TextTestResult):
    def startTest(self,test):
        super().startTest(test)
        self.names.append(test.id())
    def __init__(self,*args):
        super().__init__(*args);self.names=[]


def main():
    files=sorted(list((ROOT/'library_m25').glob('*.py'))+
                 [ROOT/'run_m25_m28.py',ROOT/'tools/verify_m25_m28.py',ROOT/'docs/M25_M28_CONTRACT.md'])
    manifest={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files}
    contract_ok=manifest['docs/M25_M28_CONTRACT.md']==CONTRACT
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromName('library_m25.tests')
    tests=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
    output=ROOT/'results/m25_m28';output.mkdir(parents=True,exist_ok=True)
    # 时间信息放独立日志；科学数据保持确定性。
    log=stream.getvalue()
    logpath=output/('tests-'+sha256(log.encode()).hexdigest()[:12]+'.log')
    logpath.write_text(log)
    try: data=study();error=None
    except Exception:data={};error=traceback.format_exc()
    counts=data.get('transfer_summary',{})
    checks=dict(contract_unchanged=contract_ok,tests_passed=tests.wasSuccessful() and not tests.skipped,
                two_generated_builders=len(data.get('builders',[]))==2 and all(r.get('accepted') for r in data.get('builders',[])),
                generated_feedback_search=bool(data.get('search',{}).get('accepted')),
                frozen_before_transfer=bool(data.get('learning_unchanged_after_transfer')),
                full_transfer_256=counts.get('full',{}).get('all_future_correct')==256,
                handwritten_tie=counts.get('full')==counts.get('handwritten'),
                json_tie=counts.get('full')==counts.get('plain_json'),
                latent_counterexample_retained=data.get('stress',{}).get('latent_errors')==[13],
                no_error=error is None)
    record=dict(status='CHECKS_PASS' if all(checks.values()) else 'CHECKS_FAIL',
                checks=checks,python=platform.python_version(),implementation=platform.python_implementation(),
                contract_commit='ab50fde9a4dc7d9d123f18c0f29183f922de986e',source_sha256=manifest,
                tests_run=tests.testsRun,test_names=tests.names,
                failures=[(t.id(),tb) for t,tb in tests.failures],errors=[(t.id(),tb) for t,tb in tests.errors],
                execution_error=error,data=data)
    raw=canonical(record);key=sha256(raw).hexdigest()
    archive=output/'runs'/(key+'.json.xz');archive.parent.mkdir(exist_ok=True)
    if archive.exists():
        if lzma.decompress(archive.read_bytes())!=raw:raise RuntimeError('archive collision')
    else:archive.write_bytes(lzma.compress(raw))
    brief={k:v for k,v in record.items() if k!='data'}
    brief.update(result_sha256=key,archive=str(archive.relative_to(ROOT)),raw_bytes=len(raw),
                 summary=counts,metaprograms=[r.get('generated_source') for r in data.get('builders',[])],
                 generated_search=data.get('search',{}).get('generated_source'))
    (output/'summary.json').write_bytes(canonical(brief))
    print(record['status'],'tests=',tests.testsRun,'result=',key)
    print(json.dumps(counts,ensure_ascii=False,sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':sys.exit(main())
