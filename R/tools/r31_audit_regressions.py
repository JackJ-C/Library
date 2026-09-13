"""Post-freeze verifier coverage tests; corrupt copies only, never raw archives."""
import copy
import hashlib
import json
import lzma
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from r31_supplemental_audit import audit_episode
from r28_r31.verify import verify_episode


def edit_body(x,index,edit):
    value=json.loads(x['ledger'][index]['body']);edit(value)
    x['ledger'][index]['body']=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n'


def mutate(x,case):
    r=x['rounds'][0]
    if case=='summary':x['summary']['updates']+=100
    elif case=='mean':r['evaluation_only']['means']['child']+=.1
    elif case=='ranking':
        edit_body(x,r['proposal_record'],lambda b:b['branches']['primary']['selection']['shortlist'].__setitem__(0,999))
    elif case=='check_link':
        def change(b):
            for key in ('old','new'):
                b['checks']['primary'][key]=[v+.001 for v in b['checks']['primary'][key]]
        edit_body(x,r['check_record'],change)
        for key in ('old','new'):r['checks']['primary'][key]=[v+.001 for v in r['checks']['primary'][key]]
    elif case=='simulation_cost':r['proposal_cost']['allocation_ast_ops']+=1
    elif case=='geometry':r['space']['dimension']+=1
    elif case=='binding':
        edit_body(x,r['check_record']+1,lambda b:b['bundle'].__setitem__('scale',.5))
    elif case=='certificate':
        edit_body(x,r['check_record'],lambda b:b['checks']['primary']['certificate'].__setitem__('distribution_certificate','PASS'))
    elif case=='previous_flag':r['previous_adopted']=not r['previous_adopted']
    else:raise ValueError(case)


def main():
    path=ROOT/'results/r28_r31/A/43100_space.json.xz'
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    original=json.loads(lzma.decompress(path.read_bytes()))
    receipts=[{'case':'unaltered_json_roundtrip','passed':audit_episode(original)['passed']}]
    for case in ('summary','mean','ranking','check_link','simulation_cost','geometry','binding','certificate','previous_flag'):
        x=copy.deepcopy(original);mutate(x,case)
        try: old_accepts=verify_episode(x)['passed']
        except (ValueError,KeyError):old_accepts=False
        message=''
        try: audit_episode(x);rejected=False
        except (ValueError,KeyError) as exc:rejected=True;message=str(exc)
        receipts.append({'case':case,'frozen_verifier_accepts_modified_copy':old_accepts,
                         'supplemental_rejects':rejected,'reason':message,'passed':old_accepts and rejected})
    assert before==hashlib.sha256(path.read_bytes()).hexdigest()
    result={'post_freeze_read_only':True,'raw_unchanged':True,'tests':receipts,
            'passed':all(r['passed'] for r in receipts),'count':len(receipts),
            'meaning':'coverage gaps reproduced; neither historical results nor learner were changed'}
    out=ROOT/'results/r28_r31/AUDIT_REGRESSIONS.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    assert result['passed']


if __name__=='__main__':main()
