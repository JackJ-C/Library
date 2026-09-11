"""Post-validation supplemental audit of matched counterfactual successor selection.
Reads frozen outputs, independently recomputes BOTH shadow selection paths; does
not import the Queen, search learner, world generator, or change any primary data.
"""
from pathlib import Path
from hashlib import sha256
import argparse,json,lzma
from verify_r12_r15 import solve,calc,total,count_nodes,need
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/r12_r15'


def expression(t):
    return str(t) if isinstance(t,(int,str)) else '('+expression(t[1])+t[0]+expression(t[2])+')'


def counter(incumbent,proposer,pool,fit,check,margin):
    desc=[]
    for ast in pool:
        fs=[]
        for p,h in fit[:3]:
            cost,H,n=solve(p,h,ast)
            fs.append((1024 if H.bit_count()==1 else 0,cost*128,1024//max(n,1),count_nodes(ast)*16))
        desc.append([sum(x[i] for x in fs)//len(fs) for i in range(4)])
    order=sorted(range(len(pool)),key=lambda i:(-calc(proposer,desc[i]),i))[:4]
    scores=sorted((total(pool[i],fit),count_nodes(pool[i]),expression(pool[i]),i) for i in order)
    best=scores[0];candidate=pool[best[-1]]
    oldfit,oldcheck,newcheck=total(incumbent,fit),total(incumbent,check),total(candidate,check)
    accept=best[0]<oldfit and newcheck<=oldcheck and (oldcheck-newcheck)/max(1,oldcheck)>=margin
    return candidate if accept else incumbent,order,accept


def audit(phase,seed):
    ptr=json.loads((OUT/f'{phase}_{seed}.json').read_text())
    raw=lzma.decompress((ROOT/ptr['archive']).read_bytes())
    need(sha256(raw).hexdigest()==ptr['sha256'],'raw mismatch')
    obj=json.loads(raw);checked=0;history_total=0
    for arm in obj['meta']:
        history=[]
        for row in arm['rounds']:
            history.extend((x['problem'],x['observed']['identified']) for x in row['live'])
            history_total+=len(row['live'])
            data=history[-32:];fit,hold=data[::2],data[1::2]
            p=row['primary'];inc=p['before']
            normal_parent=0 if arm['method']=='frozen_parent' else inc
            for key,parent,margin in [('frozen_counter',0,p['predicted_error_margin']),
                                       ('unguarded_counter',normal_parent,0)]:
                new,order,accepted=counter(inc,parent,row['pool'],fit,hold,margin)
                recorded=row[key]
                need(new==recorded['after'] and order==recorded['selected'] and accepted==recorded['accepted'],
                     f'matched successor differs {seed}/{arm["method"]}/{row["generation"]}/{key}')
                checked+=1
    return {'phase':phase,'seed':seed,'raw_sha256':ptr['sha256'],'matched_shadow_paths_checked':checked,
            'live_history_records':history_total,'status':'VERIFIED',
            'role':'post-validation supplementary recomputation, no experiment tuning'}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('A','B'));ap.add_argument('--seed',type=int,required=True)
    a=ap.parse_args();r=audit(a.phase,a.seed)
    (OUT/f'SHADOW_VERIFIED_{a.phase}_{a.seed}.json').write_text(json.dumps(r,sort_keys=True)+'\n')
    print(json.dumps(r))
