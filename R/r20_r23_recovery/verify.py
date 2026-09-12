"""Read-only, independent arithmetic replay. Does not import Queen or racing.
It verifies finite computations, not phenomenology or hostile-process execution.
"""
import json,lzma,math
from pathlib import Path
from collections import Counter


def need(ok,why):
    if not ok:raise AssertionError(why)

def eq(a,b):
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):
        return len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):return abs(a-b)<1e-10
    return a==b

def expr(t,x,names,old=False):
    if type(t) is int:return t*256 if old else float(t)
    if isinstance(t,str):return x[names.index(t)]
    a,b=expr(t[1],x,names,old),expr(t[2],x,names,old)
    if t[0]=='+':v=a+b
    elif t[0]=='-':v=a-b
    elif t[0]=='*':v=a*b//256 if old else a*b
    elif t[0]=='/':v=a*256//(abs(b)+1) if old else a/(abs(b)+.001)
    else:raise ValueError('bad op')
    limit=10**9 if old else 10**6
    return max(-limit,min(limit,v))

def nodes(t):return 1 if isinstance(t,(str,int)) else 1+nodes(t[1])+nodes(t[2])
def text(t):return str(t) if isinstance(t,(str,int)) else '('+text(t[1])+t[0]+text(t[2])+')'


def taskloss(ast,p,h):
    H=(1<<p['count'])-1;available=list(range(len(p['masks'])));cost=0
    while H.bit_count()>1:
        n=H.bit_count();c=[]
        for a in available:
            sizes=[(m&H).bit_count() for m in p['masks'][a]]
            x=((n*n-sum(s*s for s in sizes))*1024//(n*n),p['prices'][a]*128,
               sum(s>0 for s in sizes)*128,a*16)
            if x[0]>0:c.append((expr(ast,x,('info','price','spread','order'),True),-a,a))
        if not c:return (cost+1000)/100
        a=max(c)[2];answer=next(m for m in p['masks'][a] if (m>>h)&1)
        H &= answer;cost+=p['prices'][a];available.remove(a)
    return cost/100


def redo_race(ast,arms,sample,scale):
    values=[[] for _ in arms];trace=[]
    for t in range(24):
        if t<len(arms):a=t;features=[];scores=[]
        else:
            means=[sum(v)/len(v) for v in values];best=min(means);features=[]
            for m,v in zip(means,values):
                var=sum((z-m)**2 for z in v)/max(1,len(v)-1)
                features.append((m,scale*math.sqrt((var+.01)/len(v)),len(v)/24,m-best))
            scores=[expr(ast,x,('mean','uncert','visits','gap')) for x in features]
            a=min(range(len(arms)),key=lambda a:(scores[a],a))
        j=len(values[a]);v=sample(a,j);values[a].append(v)
        trace.append({'arm':a,'sample':j,'loss':v,'features':features,'scores':scores})
    means=[sum(v)/len(v) for v in values]
    best=min(range(len(arms)),key=lambda a:(means[a],nodes(arms[a]),text(arms[a])))
    v=values[best];m=means[best];var=sum((x-m)**2 for x in v)/max(1,len(v)-1)
    return best,trace,values,m,math.sqrt((var+.01)/len(v))


class Replay:
    def __init__(self,arms,history):self.arms=arms;self.history=history;self.cache={};self.inner_cache={}
    def loss(self,a,j):
        j%=len(self.history);key=(a,j)
        if key not in self.cache:self.cache[key]=taskloss(self.arms[a],*self.history[j])
        return self.cache[key]
    def inner(self,ast,split,scale):
        key=(text(ast),split,scale)
        if key in self.inner_cache:return self.inner_cache[key]
        train=[i for i in range(len(self.history)) if i%2==split%2]
        test=[i for i in range(len(self.history)) if i%2!=split%2]
        shift=(split//2)%len(train)
        best,tr,vals,m,u=redo_race(ast,self.arms,lambda a,j:self.loss(a,train[(j+shift)%len(train)]),scale)
        indices=[test[(j+split//2)%len(test)] for j in range(min(4,len(test)))]
        value=sum(self.loss(best,j) for j in indices)/len(indices)
        self.inner_cache[key]=(value,best,tr,vals,m,u)
        return self.inner_cache[key]


def check_branch(b,e):
    pool,scale=b['pool'],b['scale'];nested=b['nested'];cursor=[0]
    def sample(a,j):
        v,best,trace,values,m,u=e.inner(pool[a],j,scale)
        stored=nested[cursor[0]];cursor[0]+=1
        need(stored['arm']==a and stored['repeat']==j,'nested resource request')
        need(eq(stored['value'],v) and stored['task_chosen']==best,'nested value')
        need(eq(stored['samples'],[[t['arm'],t['sample'],t['loss']] for t in trace]),'inner allocation trace')
        return v
    best,trace,values,m,u=redo_race(b['proposer'],pool,sample,scale)
    need(cursor[0]==24,'outer budget')
    r=b['outer'];need(r['chosen']==best and eq(r['values'],values) and eq(r['mean'],m) and eq(r['uncert'],u),'outer reconstruction')
    for a,z in zip(trace,r['trace']):
        for k in ('arm','sample','loss','features','scores'):need(eq(a[k],z[k]),'pre-outcome choice '+k)
    old=[e.inner(b['parent'],s,scale)[0] for s in (10,11,12)]
    new=[e.inner(pool[best],s,scale)[0] for s in (10,11,12)]
    accepted=(text(pool[best])!=text(b['parent']) and sum(new)<sum(old)-1e-12
              and all(a<=z+1e-12 for a,z in zip(new,old)))
    need(eq(old,b['old_check']) and eq(new,b['new_check']),'adoption check')
    need(accepted==b['accepted'],'acceptance truth')
    need(eq(b['after'],pool[best] if accepted else b['parent']),'actual child')


def verify_record(r):
    history=[];ratios=[];records=r['ledger'];counts=Counter();task=0
    invalid=set()
    for i,v in enumerate(records):
        need(v['seq']==i,'record order')
        need(all(0<=k<i for k in v['refs']+v['deps']),'history edge')
        need(not any(k in invalid for k in v['deps']),'new proof already invalid')
        if v['kind']=='revocation':
            b=json.loads(v['body']);before=invalid.copy();invalid.add(b['root'])
            for z in records[:i]:
                if any(k in invalid for k in z['deps']):invalid.add(z['seq'])
            need(set(b['invalidated'])==invalid-before,'revocation closure')
    need(invalid==set(r['invalid']),'final invalid set')
    cases=[(x['problem'],x['target']) for x in r['heldout_evaluator_only']]
    gains=[];cgains=[];flags=[]
    for row in r['rounds']:
        need(eq(row['task_pool'][0],task),'continuity of deployed task function')
        for live in row['live']:
            p=live['problem'];H=(1<<p['count'])-1;price=0
            for s in live['observed']['steps']:
                need(s['before']==H,'live start')
                a,v=s['query'],s['value']
                need((p['masks'][a][v]>>live['evaluator_target'])&1,'real reply')
                H &= p['masks'][a][v];price+=p['prices'][a]
                need(s['after']==H,'live update')
                counts['live_queries']+=1
            need(H.bit_count()==1 and H.bit_length()-1==live['observed']['identified'],'identified from replies')
            need(eq(taskloss(task,p,live['observed']['identified']),price/100),'actual solver use')
            history.append((p,live['observed']['identified']))
        history=history[-32:]
        main=row['primary'];scale=sum(ratios[-12:])/len(ratios[-12:]) if ratios else 1.
        need(eq(main['scale'],scale),'self calibration uses only prior checks')
        e=Replay(row['task_pool'],history)
        for name in ('primary','frozen_counter','neutral_counter'):check_branch(row[name],e);counts['paired_choices']+=1
        need(main['prediction_key']<main['check_key'],'forecast precedes validation')
        f=json.loads(records[main['prediction_key']]['body']);c=json.loads(records[main['check_key']]['body'])
        need(eq(f['mean'],main['outer']['mean']) and eq(c['validation_losses'],main['new_check']),'raw calibration source')
        ratios.append(min(4.,max(.25,abs(sum(main['new_check'])/3-f['mean'])/max(.02,f['uncert']))))
        nextscale=sum(ratios[-12:])/len(ratios[-12:]);need(eq(row['scale_after'],nextscale),'updated self calibration')
        fit=list(range(0,len(history),2));test=list(range(1,len(history),2))
        best,tr,vals,_,_=redo_race(main['after'],row['task_pool'],lambda a,j:e.loss(a,fit[j%len(fit)]),nextscale)
        need(eq(vals,row['task_race']['values']),'task fit subset')
        old=sum(e.loss(0,j) for j in test);new=sum(e.loss(best,j) for j in test)
        task=row['task_pool'][best] if new<old-1e-12 else row['task_pool'][0]
        need(eq(task,row['task_check']['adopted']),'disjoint task adoption')
        he=Replay(row['task_pool'],cases);evals=row['evaluation_only']
        plans={'parent':main['parent'],'child':main['after'],'frozen_child':row['frozen_counter']['after'],
               'uncalibrated_child':row['neutral_counter']['after'],'initial':['-','mean','uncert'],'uniform':'visits'}
        for name,a in plans.items():
            parts=[he.inner(a,j,scale)[0] for j in range(6)]
            need(eq(parts,evals[name]['parts']),'heldout '+name)
            counts['heldout_partition_values']+=6
        p,ch,fr=(evals[n]['mean'] for n in ('parent','child','frozen_child'))
        link=row['generation']>0 and row['allocator_rebound'] and ch<p-1e-12 and ch<fr-1e-12
        need(link==row['strict_link'],'recursive link')
        flags.append(link);gains.append(fr-ch)
        cgains.append(evals['uncalibrated_child']['mean']-ch)
    need(eq(r['gain'],sum(gains[1:])/7) and eq(r['calibration_gain'],sum(cgains)/8),'aggregate intervention effect')
    need(r['consecutive']==any(a and b for a,b in zip(flags,flags[1:])),'consecutive result')
    need(all(r['pressure'].values()),'lifecycle failure')
    return dict(counts)


def load(path):return json.loads(lzma.decompress(Path(path).read_bytes()))

if __name__=='__main__':
    import sys
    for p in sys.argv[1:]:print(json.dumps({'file':p,'checked':verify_record(load(p))}))
