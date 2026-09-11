"""M29–M31 executable experiments; M32 audit is tools/audit_library.py.

Only the current repository is read/written. No network, models or paid resources.
A successful finite check is explicitly distinct from the user's universal goal.
"""
from hashlib import sha256
import io,json,lzma,platform,sys,traceback,unittest
from pathlib import Path
from library_m29.runtime import canonical
from library_m29.study import run
ROOT=Path(__file__).resolve().parent
CONTRACT='203a8c8501991ad7db42735dea22b7721e903ccdf6498a522c7f785f851365e6'
COMMIT='2665fd2928e5dee54ded59781e0d7977eb48a8ea'


class Recorded(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw);self.names=[]
    def startTest(self,test):
        self.names.append(test.id());super().startTest(test)


def main():
    files=sorted(list((ROOT/'library_m29').glob('*.py'))+list((ROOT/'library_m25').glob('*.py'))+
          [ROOT/'run_m29_m32.py',ROOT/'docs/M29_M32_CONTRACT.md',
           ROOT/'tools/verify_m29_m32.py',ROOT/'tools/audit_library.py'])
    manifest={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in files}
    contract_ok=manifest['docs/M29_M32_CONTRACT.md']==CONTRACT
    output=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromName('library_m29.tests')
    tests=unittest.TextTestRunner(stream=output,resultclass=Recorded,verbosity=2).run(suite)
    data,error={},None
    try:data=run()
    except Exception:error=traceback.format_exc()
    checks={'contract_unchanged':contract_ok,'new_unit_tests':tests.wasSuccessful() and tests.testsRun>0 and not tests.skipped,
            'experiment_executed':error is None}
    if data:
        checks.update(three_generations=len(data['generations'])==3,
          seed_disabled=all(data['seed_calls_blocked']),same_information_control=data['baseline']['equal_all_rows'],
          full_transfer=data['bridge']['transfer_summary']['full']['all_future_correct']==256,
          new_execution_guard=data['negative_results']['new_guard_denies_obsolete_execution'],
          fixed_ancestors_disclosed=not data['origin_coverage']['all_high_level_rules_autonomously_originated'])
    record={'scope':'generated_list_kernels_and_bounded_handoff_not_universal_autonomy',
            'status':'CHECKS_PASS' if all(checks.values()) else 'CHECKS_FAIL',
            'strong_goal':'NOT_ESTABLISHED','contract_commit':COMMIT,'python':platform.python_version(),
            'source_sha256':manifest,'checks':checks,'tests_run':tests.testsRun,'test_names':tests.names,
            'failures':[(t.id(),s) for t,s in tests.failures],'errors':[(t.id(),s) for t,s in tests.errors],
            'skipped':[(t.id(),s) for t,s in tests.skipped],'experiment_error':error,'data':data}
    raw=canonical(record);key=sha256(raw).hexdigest();folder=ROOT/'results/m29_m32';folder.mkdir(exist_ok=True,parents=True)
    runs=folder/'runs';runs.mkdir(exist_ok=True)
    archive=runs/(key+'.json.xz')
    if archive.exists() and lzma.decompress(archive.read_bytes())!=raw:raise RuntimeError('archive mismatch')
    if not archive.exists():archive.write_bytes(lzma.compress(raw))
    summary={k:v for k,v in record.items() if k!='data'}
    summary.update(result_sha256=key,archive=str(archive.relative_to(ROOT)),raw_bytes=len(raw),compressed_bytes=archive.stat().st_size)
    if data:summary['results']={'bootstrap':{k:{'program':r['program'],'attempts':r['attempts'],'refutations':len(r['rounds'])-1}
        for k,r in data['bootstrap'].items()},'generations':len(data['generations']),
        'all_generations_same_programs':all(r['same_programs'] for r in data['generations']),
        'bridge':data['bridge']['transfer_summary'],'fixed_ancestors':data['origin_coverage']['fixed_high_level_dependencies']}
    (folder/'summary.json').write_bytes(canonical(summary));(folder/'latest_tests.log').write_text(output.getvalue())
    print(json.dumps({'status':record['status'],'tests':tests.testsRun,'sha256':key,'strong_goal':record['strong_goal']},sort_keys=True))
    if error:print(error,file=sys.stderr)
    return 0 if all(checks.values()) else 1


if __name__=='__main__':sys.exit(main())
