"""Generic finite diagnostic-program synthesis. Development version.
Same score function ranks physical queries and shallow successor descriptors.
World/task answers are never descriptors for candidate ranking.
"""
from random import Random
from collections import Counter
from math import log2
from dataclasses import dataclass, field

VARS=('info','price','spread','order')
OPS=('+','-','*','/')

@dataclass
class Cost:
    feature_ops: int=0
    ast_ops: int=0
    simulated_queries: int=0
    actual_queries: int=0
    paid_probe_cost: int=0
    full_evaluations: int=0
    def charge(self,key,n=1): setattr(self,key,getattr(self,key)+n)

def text(t):
    if isinstance(t,(int,str)):return str(t)
    return '('+text(t[1])+t[0]+text(t[2])+')'

def nodes(t): return 1 if isinstance(t,(int,str)) else 1+nodes(t[1])+nodes(t[2])

def evaluate(t,x,c=None):
    if c:c.ast_ops+=1
    if type(t) is int:return t*256
    if isinstance(t,str):return x[VARS.index(t)]
    a,b=evaluate(t[1],x,c),evaluate(t[2],x,c)
    if t[0]=='+': y=a+b
    elif t[0]=='-':y=a-b
    elif t[0]=='*':y=a*b//256
    elif t[0]=='/':y=a*256//(abs(b)+1)
    else:raise ValueError('opcode')
    return max(-10**9,min(10**9,y))

class Program:
    def __init__(self,ast):
        self.ast=ast;self.source='score(info,price,spread,order)='+text(ast)
    def __call__(self,x,c=None):return evaluate(self.ast,x,c)

@dataclass
class Problem:
    masks: tuple
    prices: tuple
    count: int
    def features(self,H,q,c):
        sizes=[(m&H).bit_count() for m in self.masks[q]]; n=H.bit_count()
        c.feature_ops+=len(sizes)+3
        return ((n*n-sum(a*a for a in sizes))*1024//(n*n),
                self.prices[q]*128, sum(a>0 for a in sizes)*128,q*16)

class Body:
    """An opaque callable mounted in the Queen, not a supplied true-hypothesis id."""
    def __init__(self,problem,target): self._p=problem;self._h=target;self.calls=0
    def __call__(self,q):
        self.calls+=1
        return next(i for i,m in enumerate(self._p.masks[q]) if (m>>self._h)&1)

def make_problem(seed, n=32, nq=24):
    rng=Random(seed);masks=[];prices=[]
    for q in range(nq):
        categories=rng.choice((2,2,3,4,5))
        # Unequal partitions with heterogeneous prices; no task-specific priority label.
        weights=[rng.expovariate(1) for _ in range(categories)]
        labels=rng.choices(range(categories),weights=weights,k=n)
        masks.append(tuple(sum(1<<i for i,x in enumerate(labels) if x==v) for v in range(categories)))
        prices.append(rng.randrange(1,10))
    # A separating basis guarantees completion, but is not necessarily cheapest.
    for bit in range((n-1).bit_length()):
        masks.append(tuple(sum(1<<i for i in range(n) if (i>>bit)&1==v) for v in (0,1)))
        prices.append(rng.randrange(3,10))
    return Problem(tuple(masks),tuple(prices),n),rng.randrange(n)

def solve(p,call,policy,c,actual=False):
    H=(1<<p.count)-1;available=list(range(len(p.masks)));history=[];paid=0
    while H.bit_count()>1 and available:
        choices=[]
        for q in available:
            f=p.features(H,q,c)
            if f[0]>0: choices.append((policy(f,c),-q,q,f))
        if not choices: break
        _,_,q,f=max(choices)
        value=call(q)
        c.charge('actual_queries' if actual else 'simulated_queries')
        if actual:c.paid_probe_cost+=p.prices[q]
        old=H;H &= p.masks[q][value];available.remove(q);paid+=p.prices[q]
        history.append({'query':q,'value':value,'before':old,'after':H,'features':f,'price':p.prices[q]})
    return paid if H.bit_count()==1 else paid+1000, H,history

def trial_score(ast,training,c):
    c.full_evaluations+=1;policy=Program(ast);total=0
    for p,h in training:
        cost,H,_=solve(p,Body(p,h),policy,c)
        total+=cost
    return total

def first_features(ast,training,c):
    # Three behavioral pilots on previously diagnosed own executions. Count all
    # replay costs. Every meta arm receives exactly these same descriptors.
    features=[]
    for p,h in training[:3]:
        cost,H,history=solve(p,Body(p,h),Program(ast),c)
        features.append((1024 if H.bit_count()==1 else 0,cost*128,
                         1024//max(1,len(history)),nodes(ast)*16))
    return tuple(sum(f[i] for f in features)//len(features) for i in range(4))

def rand_ast(rng,depth):
    if depth==0 or rng.random()<.35:return rng.choice((0,1,2,-1)+VARS)
    return (rng.choice(OPS),rand_ast(rng,depth-1),rand_ast(rng,depth-1))

def mutate(t,rng):
    if isinstance(t,(int,str)) or rng.random()<.3:return rand_ast(rng,2)
    side=rng.randrange(2)+1;parts=list(t);parts[side]=mutate(t[side],rng)
    return tuple(parts)

def pool(incumbent,seed,count=40):
    rng=Random(seed);result=[];seen={text(incumbent)}
    for _ in range(count*20):
        x=mutate(incumbent,rng) if rng.random()<.55 else rand_ast(rng,3)
        if nodes(x)>15 or text(x) in seen:continue
        seen.add(text(x));result.append(x)
        if len(result)==count:break
    return result

def successor(incumbent,proposer,pool_,training,c,full=6):
    fit=training[::2];check=training[1::2]
    descriptors=[first_features(a,fit,c) for a in pool_]
    order=sorted(range(len(pool_)), key=lambda i:(-proposer(descriptors[i],c),i))[:full]
    old_score=trial_score(incumbent,fit,c)
    scored=[(trial_score(pool_[i],fit,c),nodes(pool_[i]),text(pool_[i]),i) for i in order]
    best=min(scored)
    new_check=trial_score(pool_[best[-1]],check,c)
    old_check=trial_score(incumbent,check,c)
    accepted=best[0]<old_score and new_check<=old_check
    return (pool_[best[-1]] if accepted else incumbent),{'selected':order,'descriptors':descriptors,
            'old_score':old_score,'scores':scored,'accepted':accepted,
            'adoption_check':[old_check,new_check], 'chosen':best[-1] if accepted else None}

