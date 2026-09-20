"""Post-frozen R37 explanatory check, evaluator-only hidden parameters.
No imports by learner; does not alter any formal trajectory.
"""
from pathlib import Path
from itertools import product
import json,lzma,hashlib

def run():
    root=Path(__file__).resolve().parents[2];base=root/'results/r32_r37_recovery';rows=[]
    for batch,first in (('A',73100),('B',74100)):
        for seed in range(first,first+16):
            p=base/batch/f'{seed}_measured.json.xz';r=json.loads(lzma.decompress(p.read_bytes()))
            d,k,op,t,g=r['fixture_evaluator_only']['parameters']
            if len(set(g))!=4 or not all(1<=x<7 for x in g):raise ValueError('theorem assumptions fail')
            def descriptor(s):
                relative=(s[0]-s[1])%7
                return relative,(s[2]<t if op=='less' else s[2]==t) if relative in (d,(-d)%7) else None
            G={tuple(s):c for s,c in r['closure']['groups']};mapping={};inverse={}
            for s,c in G.items():
                desc=descriptor(s)
                if desc in mapping and mapping[desc]!=c:raise ValueError('closed-form class splits')
                if c in inverse and inverse[c]!=desc:raise ValueError('closed-form class merges')
                mapping[desc]=c;inverse[c]=desc
            expected=8 if d==0 else 9
            if len(mapping)!=expected or r['closure']['refinements']!=[1,3 if d==0 else 5,expected,expected]:raise ValueError('two-step family theorem')
            metric=json.loads((base/'audit'/f'{seed}_sequence_metric.json').read_bytes());states=metric['states']
            for i,c in enumerate(states):
                for j,e in enumerate(states):
                    value='0' if c==e else ('1/2' if inverse[c][1] is None and inverse[e][1] is None else '1')
                    if metric['matrix'][i][j]!=value:raise ValueError('closed-form distance theorem')
            rows.append({'seed':seed,'batch':batch,'d':d,'expected_classes':expected,'observed_classes':len(mapping),'refinements':r['closure']['refinements'],'closed_form_and_metric_match':True})
    (base/'FAMILY_THEOREM_CHECKS.json').write_text(json.dumps({'post_hoc':True,'proof_parameter_configurations':50400,'actual_seed_checks':len(rows),'rows':rows},indent=2)+'\n')
    print('FAMILY_THEOREM_CHECKS',len(rows),'passed')
if __name__=='__main__':run()
