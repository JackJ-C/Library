"""Independent read-only arithmetic/archive verification. No Queen, World, learning
module, evaluator class, or experiment runner is imported by this verifier.
It does not prove consciousness, hostile-process safety or all implementation properties.
"""
from pathlib import Path
from hashlib import sha256
from collections import defaultdict
import json,lzma,argparse
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/r12_r15'


def need(ok,why):
    if not ok:raise AssertionError(why)

def calc(t,x):
    if type(t) is int:return t*256
    if isinstance(t,str):return x[('info','price','spread','order').index(t)]
    op,left,right=t;a,b=calc(left,x),calc(right,x)
    if op=='+':v=a+b
    elif op=='-':v=a-b
    elif op=='*':v=a*b//256
    elif op=='/':v=a*256//(abs(b)+1)
    else:raise ValueError('unknown generated operation')
    return max(-10**9,min(10**9,v))

def info(p,H,q):
    n=H.bit_count();sizes=[(m&H).bit_count() for m in p['masks'][q]]
    return ((n*n-sum(s*s for s in sizes))*1024//(n*n),p['prices'][q]*128,
            sum(s>0 for s in sizes)*128,q*16)

def solve(p,h,ast,trace=None):
    H=(1<<p['count'])-1;available=list(range(len(p['masks'])));paid=0;k=0
    while H.bit_count()>1:
        candidates=[]
        for q in available:
            f=info(p,H,q)
            if f[0]>0:candidates.append((calc(ast,f),-q,q,f))
        if not candidates:break
        _,_,q,f=max(candidates)
        v=next(j for j,m in enumerate(p['masks'][q]) if (m>>h)&1)
        after=H&p['masks'][q][v]
        if trace is not None:
            r=trace[k]
            need(r['query']==q and r['value']==v and r['before']==H and r['after']==after,'query sequence')
            need(list(f)==r['features'] and p['prices'][q]==r['price'],'query features or price')
        k+=1;paid+=p['prices'][q];H=after;available.remove(q)
    if trace is not None:need(k==len(trace),'unverified suffix')
    return paid if H.bit_count()==1 else paid+1000,H,k

def total(ast,cases):return sum(solve(p,h,ast)[0] for p,h in cases)
def count_nodes(t):return 1 if isinstance(t,(str,int)) else 1+count_nodes(t[1])+count_nodes(t[2])

def verify_ledger(records,invalid_final):
    invalid=set();children=defaultdict(list);bodies=[]
    for i,r in enumerate(records):
        need(r['seq']==i,'ledger order')
        body=json.loads(r['body']);bodies.append(body)
        for k in ('refs','deps'):need(len(r[k])==len(set(r[k])) and all(type(x)is int and 0<=x<i for x in r[k]),'illegal evidence link')
        for d in r['deps']:
            need(d not in invalid,'new claim with already retracted support');children[d].append(i)
        if r['kind']=='revocation':
            todo=[body['root']];changed=set()
            while todo:
                at=todo.pop()
                if at in invalid:continue
                invalid.add(at);changed.add(at);todo+=children[at]
            need(sorted(changed)==body['invalidated'],'wrong retraction propagation')
        if r['kind']=='R12_interpretation':
            intent,obs=r['refs'];need(set((intent,obs))<=set(r['deps']),'semantic support missing')
            need(not bodies[intent]['checked'],'unexecuted fast answer acquired a label')
        if r['kind']=='R12_monitor_model':
            cells=defaultdict(lambda:[1,2]);tot=[1,2]
            for key in body['mapping']['support']:
                need(key in r['deps'],'monitor sample is decorative history')
                j,k=records[key]['refs'];a=bodies[j];z=bodies[k]
                decoded=[[(v-off)%7 for v in row] for off,row in zip(a['offsets'],z['after']['workers'])]
                correct=decoded[0]==decoded[1] and decoded[0][a['object']]==a['goal']
                cell=(a['trace']['repeats'],sum(a['trace']['margin']>v for v in (.20,.55,1.1)))
                cells[cell][0]+=correct;cells[cell][1]+=1;tot[0]+=correct;tot[1]+=1
            need([[*k,*v] for k,v in sorted(cells.items())]==body['mapping']['cells'],'model does not match raw intentions/outcomes')
            need(tot==body['mapping']['global'],'model mean')
    need(invalid==set(invalid_final),'invalid final state')
    return bodies

def probability(mapping,trace):
    k=(trace['repeats'],sum(trace['margin']>v for v in (.20,.55,1.1)))
    for r,b,a,n in mapping['cells']:
        if (r,b)==k:return a/n
    return .5

def verify_online(episodes,ledger,bodies):
    primary=next(e for e in episodes if e['method']=='adaptive');n=0
    for e in episodes:
        need(e['same_queen'] and e['same_ledger'],'continuity assertion missing')
        correct=checked=rawc=unknown=0;bs=0
        s,g=e['physics_evaluator_only']['emitter'],e['physics_evaluator_only']['gain']
        for r,matched in zip(e['rows'],primary['rows']):
            need(all(r[k]==matched[k] for k in ('t','positions','object','goal','raw','trace')),'first-order answers not matched')
            obj,goal=r['object'],r['goal'];pos=r['positions'][obj]
            raw=(pos+s*g*r['raw'])%7==goal
            actual=(pos+s*g*r['request'])%7==goal
            need(raw==r['raw_correct_evaluator'] and actual==r['observed_correct'],'action arithmetic')
            if r['checked']:need(r['label'] is None,'checked output became fast-answer training target')
            if e['method']=='adaptive':
                a,z=bodies[r['intention']],bodies[r['observation']]
                need(r['intention']<r['observation'],'post-outcome intention')
                need(a['trace']==r['trace'] and a['probability']==r['probability'] and a['request']==r['request'],'prospective record mismatch')
                decoded=[[(v-off)%7 for v in row] for off,row in zip(a['offsets'],z['after']['workers'])]
                need(decoded[0][obj]==(pos+s*g*r['request'])%7,'actual Worker receipt')
                if r['status']=='supported':
                    need(r['model_before']<r['intention'],'forecast uses future model')
                    mapping=bodies[r['model_before']]['mapping']
                    need(probability(mapping,r['trace'])==r['probability'],'forecast not obtained from current model')
            rawc+=raw;correct+=actual;checked+=r['checked'];unknown+=r['status']=='unknown'
            bs+=((.5 if r['probability'] is None else r['probability'])-raw)**2;n+=1
        for start in range(0,512,32):need(sum(r['checked'] for r in e['rows'][start:start+32])==8,'unequal online review budget')
        c=e['counts'];need(correct==c['correct'] and rawc==c['raw_correct'] and checked==c['checked'] and unknown==c['unknown'],'online totals')
        need(abs(bs/512-e['brier'])<1e-12,'Brier mismatch')
        if e['method'] in ('plain','compiled'):need(e['rows']==primary['rows'],'ordinary equivalent controller mismatch')
    return n

def verify_meta(e):
    history=[];errors=[];last=0;checked=0
    cases=[(x['problem'],x['gold_evaluator_only']) for x in e['heldout']]
    for r in e['rounds']:
        p=r['primary'];need(p['before']==last,'broken parent lineage')
        for own in r['live']:
            pp=own['problem'];observed=own['observed'];h=observed['identified']
            cost,H,_=solve(pp,h,last,observed['steps'])
            need(H==(1<<h) and h==own['gold_evaluator_only'] and cost==observed['price'],'own process not actually identified')
            history.append((pp,h));checked+=1
        data=history[-32:];fit=data[::2];hold=data[1::2];pool=r['pool']
        descriptors=[]
        for t in pool:
            fs=[]
            for pp,h in fit[:3]:
                cost,H,n=solve(pp,h,t)
                fs.append((1024 if H.bit_count()==1 else 0,cost*128,1024//max(1,n),count_nodes(t)*16))
            descriptors.append([sum(f[i] for f in fs)//len(fs) for i in range(4)])
        if e['method']=='fixed_margin':margin=.05
        elif e['method']=='unguarded':margin=0
        else:margin=(sum(errors[-16:])/len(errors[-16:]) if errors else 0)*.5
        parent=0 if e['method']=='frozen_parent' else last
        need(descriptors==p['descriptors'],'candidate pilot descriptors')
        order=sorted(range(len(pool)),key=lambda i:(-calc(parent,descriptors[i]),i))[:4]
        need(order==p['selected'],'actual parent does not select successors')
        need(abs(p['predicted_error_margin']-margin)<1e-12,'meta reliability not predicted from past only')
        oldfit=total(last,fit);oldhold=total(last,hold)
        for score in p['scores']:need(total(pool[score[3]],fit)==score[0],'full fit score')
        best=min(p['scores']);candidate=pool[best[3]];newhold=total(candidate,hold)
        gf=(oldfit-best[0])/max(1,oldfit);gc=(oldhold-newhold)/max(1,oldhold)
        accepted=best[0]<oldfit and newhold<=oldhold and gc>=margin
        need(accepted==p['accepted'] and oldhold==p['old_check'] and newhold==p['new_check'],'candidate acceptance')
        new=candidate if accepted else last
        need(new==p['after'] and accepted==r['actual_rebind'],'real program update')
        errors.append(abs(gf-gc))
        bc=total(last,cases);nc=total(new,cases)
        fc=total(r['frozen_counter']['after'],cases);uc=total(r['unguarded_counter']['after'],cases)
        need((bc,nc,fc,uc)==(r['before_cost'],r['current_cost'],r['frozen_cost'],r['unguarded_cost']),'independent heldout scores')
        for trace,(pp,h) in zip(r['current_replay'],cases):need(solve(pp,h,new,trace['steps'])[0]==trace['price'],'deployment replay')
        strict=r['generation']>0 and accepted and nc<bc and nc<fc
        need(strict==r['strict_link'] and (nc>bc)==r['regression'],'recursive effect classification')
        last=new
    need(e['same_queen'] and e['same_ledger'],'meta continuity')
    need(sum(r['strict_link'] for r in e['rounds'])==e['strict_links'],'link aggregate')
    return checked

def verify_one(pointer):
    p=json.loads(pointer.read_text());path=ROOT/p['archive']
    need(path.resolve().is_relative_to(ROOT),'archive path escapes R')
    raw=lzma.decompress(path.read_bytes());need(sha256(raw).hexdigest()==p['sha256'],'raw hash')
    r=json.loads(raw)
    for name,h in r['sources'].items():need(sha256((ROOT/name).read_bytes()).hexdigest()==h,'changed source: '+name)
    main=r['meta'][0];need(main['continued_from_online'],'not the same Queen across domains')
    bodies=verify_ledger(main['ledger'],main['invalid'])
    online=verify_online(r['online'],main['ledger'],bodies)
    diagnoses=sum(verify_meta(e) for e in r['meta'])
    return {'seed':r['seed'],'phase':r['phase'],'raw_sha256':p['sha256'],
            'online_executions':online,'search_diagnoses':diagnoses,
            'records_checked':len(main['ledger']),'status':'VERIFIED'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('dev','A','B'));ap.add_argument('--seed',type=int,required=True)
    a=ap.parse_args();v=verify_one(OUT/f'{a.phase}_{a.seed}.json')
    (OUT/f'VERIFIED_{a.phase}_{a.seed}.json').write_text(json.dumps(v,sort_keys=True)+'\n')
    print(json.dumps(v))
if __name__=='__main__':main()
