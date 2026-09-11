"""Explicit suite/archive inventory. Runs only a copy of this repository.

This is not a complete security audit or formal proof. Missing files/suites are
reported rather than counted as passing. No network, git credentials or services.
"""
import argparse,ast,hashlib,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SUITES=('tests.test_m0','tests.test_m1_m7','library_m8.tests','library_m12.tests',
        'library_m16.tests','library_m21.tests','library_m25.tests','library_m29.tests')
VERIFIERS=('tools/verify.py','tools/m8_evidence.py','tools/verify_m12_m15.py',
           'tools/verify_m16_m20.py','tools/verify_m21_m24.py','tools/verify_m25_m28.py',
           'tools/verify_m29_m32.py')
TREE_EXPECTED={'library_m8':'b82f099e600f147311ccb036fb9ed9a3064160c4',
 'library_m12':'3766fd146b9ab5dd30237a3489a529edcd9e969d',
 'library_m16':'4617dac44690443af3515af1ae5188b05a6eb238',
 'library_m25':'5bb568fe60a6cbb563d8cebfe546cfc2a2eedf84'}
SINGLE_EXPECTED={'run_m8_m11.py':'5b8c7e78df2d845fca35ff270be60bbab11a4f99',
 'run_m12_m15.py':'cb4338bb33f761b79d7086772e1efb2bb7fd9b58',
 'run_m16_m20.py':'fe887886f50a6533e88aef6eb3f5f2c288c89dee',
 'run_m25_m28.py':'774bb40842563bc2f97d3c5efcfc390df1e6e6a7',
 'tools/m8_evidence.py':'0746949a80b8f89e25d660ce2370af92d71c3d38',
 'tools/verify_m12_m15.py':'c5f552db7660f1e4c0a9ca3da6e760189872cfa5',
 'tools/verify_m16_m20.py':'8726b39fff91f9c46a6e63fe5e2e0d1b65a1150c',
 'tools/verify_m25_m28.py':'93a12b3d28b46d62c9c2c12a0f2c5845dd648437'}


MISSING_AT_BASELINE={
 'library_m0/__init__.py':'217605151a96fb856a06579ee77d48e0806e3ee0',
 'library_m0/core.py':'a7720c254a3b3fc0aa2179ccab7004a9147501ec',
 'library_m0/witnesses.py':'f6b02b028d4b07cd5238ef4e5ece734560e6bc83',
 'library_m21/__init__.py':'0bf3591d2aad4ddf85d9450bcb1bea04244ead43',
 'library_m21/engine.py':'3651a8f1f5ad7b38eef54c5201d776f93d2f03c3',
 'library_m21/study.py':'55211c82999fc16bb2ac34006ef4f85ac92d5c96',
 'library_m21/synthesis.py':'3e42fed52bb790028221a87ac81cf6883718d7be',
 'library_m21/tests.py':'fb303a7015eca2f1b20a5849d1f2de820f168fdf',
 'tests/__init__.py':'73f69c2d90bc87526cc2b8701d181bef805b9e4e',
 'tests/test_m0.py':'d8b2a8db2928d2c7dce56d22b294ebbd9a41f2b5',
 'tests/test_m1_m7.py':'c758805c5f69bc8f4fc4feb1ede2ac3ffba0412a',
 'library_experiments.py':'e2eed33b2fdbed1ddef8f09377b591662f4d5d69',
 'run_m0.py':'ef728dc6978845139fb7752f6d84bc94d53a3703',
 'run_m1_m6.py':'760920a7abeef320dbf1e0634626d3634df23817',
 'run_m7.py':'cb7fd7a382f3203d474ab71a78de6d3997375840',
 'run_m21_m24.py':'1dace9a9d9b0cd477fa254d6e22552b435b69106',
 'tools/verify.py':'69f5ec511a48662fdf301220e6c0605705ccc4b4',
 'tools/verify_m21_m24.py':'f5bdd6f9dbcd65d6b2048fe31becd1c2e31560e9',
 'tools/restore_m21_first_record.py':'ddd9f63a9b2d0024ef2e62ede6aaf18cd3096e1a'}


def pack(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
def blob(data,kind='blob'):return hashlib.sha1(kind.encode()+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()
def git_tree(folder):
    entries=[]
    for p in sorted(folder.iterdir(),key=lambda p:p.name+('/' if p.is_dir() else '')):
        if p.name=='__pycache__':continue
        if p.is_dir():mode,key='40000',git_tree(p)
        else:mode,key='100644',blob(p.read_bytes())
        entries.append(mode.encode()+b' '+p.name.encode()+b'\0'+bytes.fromhex(key))
    return blob(b''.join(entries),'tree')


def commands(copy,output):
    rows=[]
    for kind,names in [('suite',SUITES),('archive',VERIFIERS)]:
        for name in names:
            path=name.replace('.','/')+'.py' if kind=='suite' else name
            if not (copy/path).is_file():
                rows.append({'kind':kind,'name':name,'status':'NOT_AVAILABLE','missing':path});continue
            args=[sys.executable,'-m','unittest',name,'-v'] if kind=='suite' else [sys.executable,name]
            try:
                p=subprocess.run(args,cwd=copy,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                 timeout=40,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                log=p.stdout;status='PASS' if p.returncode==0 else 'FAIL'
                row={'kind':kind,'name':name,'status':status,'returncode':p.returncode,
                     'command':' '.join(['python3']+args[1:]),'working_directory':'isolated_repository_copy'}
            except subprocess.TimeoutExpired as exc:
                log=exc.stdout or '';log=log.decode(errors='replace') if isinstance(log,bytes) else log
                row={'kind':kind,'name':name,'status':'TIMEOUT','limit_seconds':40}
            logname=kind+'_'+name.replace('/','_').replace('.','_')+'.log'
            (output/logname).write_text(log);row['log']=logname
            if kind=='suite':
                m=re.search(r'Ran (\d+) tests?',log);row['tests_run']=int(m[1]) if m else None
            rows.append(row)
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--strict',action='store_true');args=parser.parse_args()
    out=ROOT/'results/m29_m32/audit';out.mkdir(parents=True,exist_ok=True)
    manifest={};imports={};syntax=[]
    for p in sorted(ROOT.rglob('*.py')):
        if any(x in p.parts for x in ('__pycache__','.venv','.git')):continue
        rel=str(p.relative_to(ROOT));raw=p.read_bytes();manifest[rel]=hashlib.sha256(raw).hexdigest()
        try:module=ast.parse(raw)
        except SyntaxError as exc:syntax.append({'file':rel,'error':str(exc)});continue
        imports[rel]=[{'module':n.module,'level':n.level} for n in ast.walk(module) if isinstance(n,ast.ImportFrom)]
    verified=[]
    for name,expected in TREE_EXPECTED.items():
        actual=git_tree(ROOT/name) if (ROOT/name).is_dir() else None
        verified.append({'path':name,'kind':'tree','expected':expected,'actual':actual,'matches':actual==expected})
    for name,expected in SINGLE_EXPECTED.items():
        actual=blob((ROOT/name).read_bytes()) if (ROOT/name).is_file() else None
        verified.append({'path':name,'kind':'blob','expected':expected,'actual':actual,'matches':actual==expected})
    with tempfile.TemporaryDirectory(prefix='Library-audit-') as tmp:
        copy=Path(tmp)/'Library'
        shutil.copytree(ROOT,copy,ignore=shutil.ignore_patterns('__pycache__','.git','audit'))
        runs=commands(copy,out)
        # Demonstrate the difference between root discovery and tests/ only.
        for name,cmd in [('discovery_root',['-m','unittest','discover','-v']),
                         ('discovery_tests_directory',['-m','unittest','discover','-s','tests','-v'])]:
            try:
                p=subprocess.run([sys.executable]+cmd,cwd=copy,text=True,stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,timeout=40,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
                (out/(name+'.log')).write_text(p.stdout)
                m=re.search(r'Ran (\d+) tests?',p.stdout)
                runs.append({'kind':'discovery','name':name,'status':'PASS' if p.returncode==0 else 'FAIL',
                             'tests_run':int(m[1]) if m else None,'returncode':p.returncode})
            except subprocess.TimeoutExpired:runs.append({'kind':'discovery','name':name,'status':'TIMEOUT'})
    # Reproduce a public-interface lifecycle failure without changing old files.
    sys.path.insert(0,str(ROOT))
    from library_m8.core import PolynomialReader
    from library_m12.guard import RevocableReader
    lifecycle=[]
    for cls in (PolynomialReader,RevocableReader):
        reader=cls(3)
        for x in range(8):reader.observe(x,0)
        before=reader.certify_full_universe();error=None
        try:reader.observe(0,1)
        except ValueError as e:error=str(e)
        lifecycle.append({'class':cls.__name__,'valid_before':before,'exception':error,
                          'valid_after':reader.certify_full_universe()})
    study_text=(ROOT/'library_m8/study.py').read_text()
    gaps=[r['name'] for r in runs if r['status']!='PASS']
    gaps.extend(r['path'] for r in verified if not r['matches'])
    remaining=[]
    for name,key in MISSING_AT_BASELINE.items():
        path=ROOT/name
        actual=blob(path.read_bytes()) if path.is_file() else None
        remaining.append({'path':name,'remote_blob':key,'available':actual is not None,
                          'hash_matches':actual==key if actual else None})
    result={'status':'AUDITED_WITH_GAPS' if gaps or syntax else 'CHECKS_PASS_WITH_SCOPE_LIMITS',
            'baseline_commit':'2665fd2928e5dee54ded59781e0d7977eb48a8ea','python':sys.version.split()[0],
            'scope':'available authenticated packages plus repository-wide structural review; not full clone',
            'historical_missing_inventory':remaining,'historical_python_files_in_inventory':46,
            'source_manifest':manifest,'source_files_seen':len(manifest),'imports':imports,
            'syntax_errors':syntax,'authenticated_baseline_paths':verified,'commands':runs,
            'unverified_or_failed':gaps,'lifecycle_reproduction':lifecycle,
            'old_m8_still_instantiates_unguarded_reader':'PolynomialReader(' in study_text,
            'all_old_experiments_rerun':False,'whole_persistent_queen_integration_verified':False}
    (out/'audit.json').write_bytes(pack(result))
    print(json.dumps({k:v for k,v in result.items() if k in ('status','source_files_seen','unverified_or_failed','lifecycle_reproduction')},ensure_ascii=False))
    return 1 if args.strict and (gaps or syntax) else 0


if __name__=='__main__':sys.exit(main())
