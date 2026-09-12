"""Typed resource allocator: the same loss/uncertainty features at both levels.
No evaluator holdouts enter this module. Fixed arithmetic grammar is disclosed.
"""
from collections import Counter
from math import sqrt
from random import Random
from r4_r7 import search

VARS=('mean','uncert','visits','gap')
INITIAL=('-', 'mean','uncert')
UNIFORM='visits'


def freeze(t):return tuple(freeze(x) for x in t) if isinstance(t,(tuple,list)) else t

def text(t):return str(t) if isinstance(t,(int,str)) else '('+text(t[1])+t[0]+text(t[2])+')'

def size(t):return 1 if isinstance(t,(int,str)) else 1+size(t[1])+size(t[2])

def compute(t, x, costs=None):
    if costs is not None:costs['allocation_ast_ops']+=1
    if type(t) is int:return float(t)
    if isinstance(t,str):return x[VARS.index(t)]
    a,b=compute(t[1],x,costs),compute(t[2],x,costs)
    if t[0]=='+':v=a+b
    elif t[0]=='-':v=a-b
    elif t[0]=='*':v=a*b
    elif t[0]=='/':v=a/(abs(b)+.001)
    else:raise ValueError('unknown operator')
    return max(-1e6,min(1e6,v))


class Program:
    def __init__(self,ast):
        self.ast=freeze(ast)
        def validate(t):
            if type(t) is int:return
            if isinstance(t,str):
                if t not in VARS:raise ValueError('unknown allocation input')
                return
            if not isinstance(t,tuple) or len(t)!=3 or t[0] not in ('+','-','*','/'):raise ValueError('bad expression')
            validate(t[1]);validate(t[2])
        validate(self.ast)
        if size(self.ast)>15:raise ValueError('expression too large')
    def __call__(self,features,costs=None):return compute(self.ast,features,costs)


def candidates(parent,seed,count=8):
    """Same fixed bounded generative prior, not a table of correct successor algorithms."""
    rng=Random(seed);out=[freeze(parent)];seen={text(parent)}
    def rand(d):
        if d==0 or rng.random()<.4:return rng.choice(VARS+(0,1,2,-1))
        return (rng.choice(('+','-','*','/')),rand(d-1),rand(d-1))
    def mutate(t):
        if isinstance(t,(int,str)) or rng.random()<.3:return rand(2)
        j=rng.choice((1,2));r=list(t);r[j]=mutate(t[j]);return tuple(r)
    for _ in range(1000):
        a=mutate(parent) if rng.random()<.6 else rand(2)
        if size(a)>15 or text(a) in seen:continue
        seen.add(text(a));out.append(a)
        if len(out)==count:return out
    raise RuntimeError('candidate generation exhausted')


def race(program, arms, sample, budget=24, scale=1., costs=None):
    if budget<len(arms):raise ValueError('budget must cover one sample per arm')
    costs=costs if costs is not None else Counter()
    values=[[] for _ in arms];trace=[]
    for step in range(budget):
        if step<len(arms):chosen=step;features=[];scores=[]
        else:
            means=[sum(v)/len(v) for v in values];best=min(means)
            features=[]
            for v,m in zip(values,means):
                var=sum((z-m)**2 for z in v)/max(1,len(v)-1)
                # An engineering uncertainty surrogate, not a confidence bound.
                u=scale*sqrt((var+.01)/len(v))
                features.append((m,u,len(v)/budget,m-best))
            scores=[program(f,costs) for f in features]
            chosen=min(range(len(arms)),key=lambda i:(scores[i],i))
        index=len(values[chosen])
        value=float(sample(chosen,index));values[chosen].append(value)
        costs['loss_requests']+=1
        trace.append({'arm':chosen,'sample':index,'loss':value,'features':features,'scores':scores})
    means=[sum(v)/len(v) for v in values];best=min(range(len(arms)),key=lambda i:(means[i],size(arms[i]),text(arms[i])))
    v=values[best];m=means[best];var=sum((z-m)**2 for z in v)/max(1,len(v)-1)
    return best,{'values':values,'means':means,'chosen':best,'mean':m,
                 'uncert':sqrt((var+.01)/len(v)),'trace':trace}


class Engine:
    """Counterfactual evaluation only over already inferred own mechanisms."""
    def __init__(self,task_pool,history):
        self.task_pool=task_pool;self.history=history;self.cache={};self.cost=Counter()
    def loss(self,arm,index):
        index%=len(self.history);key=(text(self.task_pool[arm]),index)
        self.cost['solver_loss_requests']+=1
        if key not in self.cache:
            p,h=self.history[index];c=search.Cost()
            value,H,trace=search.solve(p,search.Body(p,h),search.Program(self.task_pool[arm]),c)
            self.cost['solver_queries']+=c.simulated_queries
            self.cost['solver_ast_ops']+=c.ast_ops;self.cost['solver_features']+=c.feature_ops
            self.cache[key]=value/100.
        else:self.cost['solver_cache_hits']+=1
        return self.cache[key]
    def inner(self,ast,split,scale=1.):
        """Fit on one parity, check on the other; only prior observed history."""
        n=len(self.history)
        train=[i for i in range(n) if i%2==split%2]
        test=[i for i in range(n) if i%2!=split%2]
        if not train or not test:raise ValueError('insufficient paired history')
        shift=(split//2)%len(train)
        best,record=race(Program(ast),self.task_pool,
            lambda a,j:self.loss(a,train[(j+shift)%len(train)]),scale=scale,costs=self.cost)
        # Four validation examples per simulation; overlapping splits are not independent samples.
        indices=[test[(j+split//2)%len(test)] for j in range(min(4,len(test)))]
        loss=sum(self.loss(best,j) for j in indices)/len(indices)
        return loss,best,record


def select_successor(parent, pool, engine, scale):
    nested=[]
    def measurement(arm,j):
        value,best,r=engine.inner(pool[arm],j,scale)
        nested.append({'arm':arm,'repeat':j,'value':value,'task_chosen':best,'inner':r})
        return value
    chosen,outer=race(Program(parent),pool,measurement,scale=scale,costs=engine.cost)
    return chosen,outer,nested


def validation(ast,engine,scale):
    return [engine.inner(ast,split,scale)[0] for split in (10,11,12)]


def accept(new,old):
    return sum(new)<sum(old)-1e-12 and all(a<=b+1e-12 for a,b in zip(new,old))
