"""Fixed operation semantics, not autonomously created rules.
Generated programs are complete conditional trees executed by these machines.
"""
from dataclasses import dataclass
from hashlib import sha256
import json


def canonical(x):
    return (json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(x):return sha256(canonical(x)).hexdigest()
def tree(x):return tuple(tree(v) for v in x) if isinstance(x,(tuple,list)) else x
def nodes(p):return 1+sum(nodes(v) for v in p[1:])


class FuelExhausted(RuntimeError):pass
class SemanticError(ValueError):pass


@dataclass
class Meter:
    limit:int
    steps:int=0
    predicates:int=0
    mappings:int=0
    def tick(self):
        if type(self.limit)is not int or self.limit<1:raise SemanticError('positive finite fuel required')
        if self.steps>=self.limit:raise FuelExhausted('VM fuel exhausted')
        self.steps+=1


class Stream:
    def __init__(self,values):self.it,self.cache,self.done=iter(values),[],False
    def empty(self,i):
        while len(self.cache)<=i and not self.done:
            try:self.cache.append(next(self.it))
            except StopIteration:self.done=True
        return i>=len(self.cache)
    def at(self,i):
        if self.empty(i):raise SemanticError('head of empty stream')
        return self.cache[i]


LEAVES={'find':('none','here','recur'),'flatmap':('nil','mapped','raw','recur')}
BRANCHES={'find':('empty','hit'),'flatmap':('empty','join')}


def validate(p,kind):
    if not isinstance(p,tuple) or not p:raise SemanticError('tuple program required')
    if p[0] in LEAVES[kind] and len(p)==1:return
    if p[0] in BRANCHES[kind] and len(p)==3:
        validate(p[1],kind);validate(p[2],kind);return
    raise SemanticError('invalid typed instruction')


def run_find(program,values,predicate,limit=1000000):
    p=tree(program);validate(p,'find');s=Stream(values);i=0;current=p;m=Meter(limit)
    while True:
        m.tick();op=current[0]
        if op=='none':return None,m
        if op=='here':s.at(i);return i,m
        if op=='recur':i+=1;current=p
        elif op=='empty':current=current[1] if s.empty(i) else current[2]
        elif op=='hit':
            item=s.at(i);m.predicates+=1;hit=predicate(item)
            if type(hit)is not bool:raise SemanticError('boolean predicate required')
            current=current[1] if hit else current[2]


def run_flatmap(program,values,mapper,limit=1000000):
    # Explicit evaluator stack and ropes avoid Python recursion and quadratic copies.
    p=tree(program);validate(p,'flatmap');xs=tuple(values);m=Meter(limit)
    todo=[('eval',p,0)];stack=[]
    while todo:
        m.tick();action,c,i=todo.pop()
        if action=='join':
            right,left=stack.pop(),stack.pop();stack.append(('branch',left,right));continue
        op=c[0]
        if op=='nil':stack.append(('leaf',()))
        elif op=='raw':stack.append(('leaf',xs[i:]))
        elif op=='mapped':
            if i>=len(xs):raise SemanticError('mapped head of empty sequence')
            m.mappings+=1;stack.append(('leaf',tuple(mapper(xs[i]))))
        elif op=='recur':todo.append(('eval',p,i+1))
        elif op=='empty':todo.append(('eval',c[1] if i>=len(xs) else c[2],i))
        elif op=='join':todo.extend([('join',None,0),('eval',c[2],i),('eval',c[1],i)])
    if len(stack)!=1:raise SemanticError('invalid stack')
    out=[];pending=[stack[0]]
    while pending:
        m.tick();r=pending.pop()
        if r[0]=='leaf':out.extend(r[1])
        else:pending.extend([r[2],r[1]])
    return tuple(out),m


def readable(p,kind):
    atoms={'none':'None','nil':'()','here':'head(xs)','raw':'xs',
           'mapped':'expand(head(xs))','recur':'self(tail(xs), callback)'}
    if p[0] in atoms:return atoms[p[0]]
    a,b=readable(p[1],kind),readable(p[2],kind)
    if p[0]=='join':return '('+a+' ++ '+b+')'
    c='empty(xs)' if p[0]=='empty' else 'accept(head(xs))'
    return '('+a+' if '+c+' else '+b+')'
