"""Post-freeze independent checks that do not alter the learner or earlier evidence."""
from pathlib import Path
from hashlib import sha256,sha1
import json,lzma,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from verify_m45_m48 import independent_pairs,require,ALL


def main():
    n=0;past=0;phases={}
    for phase in ('A','B'):
        s=json.loads((ROOT/f'results/m45_m48/{phase}.json').read_text())
        raw=lzma.decompress((ROOT/s['archive']).read_bytes());require(sha256(raw).hexdigest()==s['sha256'],'archive hash')
        d=json.loads(raw);this=0
        for row in d['batch']['rows']:
            if row['method']!='library':continue
            records=row['ledger']
            for r in records:
                if r['kind']!='source_model_review':continue
                result=json.loads(r['body'])['data']['result'];joint=set(ALL)
                for group in result['groups']:
                    commands=[];packet=None
                    for k in group['evidence']:
                        rr=records[k];bb=json.loads(rr['body'])['data']
                        if rr['kind']=='explore_intention':commands.append((bb['object'],bb['command']))
                        else:packet=bb['packet']
                    joint &={tuple(m) for _,m in independent_pairs(commands,packet)}
                require(sorted(map(list,joint))==result['models'],'aggregate model set not supported')
                this+=1;n+=1
        phases[phase]={'aggregated_model_sets_recomputed':this}
    remote={'library_m41/__init__.py':'c3c3f39e7a0f46337d4135b031ab6b7262d287b6',
        'library_m41/integration.py':'76d31a26a3668296185e24074f69c0ddffde6374',
        'library_m41/tests.py':'c3cf5d0e6bf360f8027d6874a8fe4d0953a6d4c1'}
    authenticated={}
    for p,h in remote.items():
        b=(ROOT/p).read_bytes();actual=sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
        require(actual==h,'remote base mismatch '+p);authenticated[p]=actual
    summary={'status':'ADDITIONAL_CHECKS_PASS','aggregate_sets_recomputed':n,'phases':phases,
        'base_commit':'a107e655e5a5c4d9dd00a3032ee8d190c8eea4a6','three_git_blob_hashes_compared_with_live_connector':authenticated,
        'audit_limitations':[
          'M45 main reviews mostly use the current observation interval; older-record utility separately tested in M48.',
          'Counterfactual task logging only in library/plain increases later metadata scan costs; do not compare total compute as if identical.',
          'marginal control omits persistent identity_beliefs only; it still computes source-mechanism compatibility.',
          'No entire-repository audit or all historical main experiments rerun.',
          'Supported nonlinear family was specified in advance; state-dependent outside-family repair failed.',
          'GitHub write tools unavailable and CLI DNS failed; no remote commit or PR created.'
        ]}
    (ROOT/'results/m45_m48/additional_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
