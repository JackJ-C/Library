"""Data-constructed conditional trees. No complete dynamics catalogue.
Fixed prior: effect = nonzero state-dependent gain times command in Z7.
"""
from itertools import product
from collections import Counter
from functools import lru_cache
P=7
FIELDS=('position','other','object','last')
STATES=tuple(product(range(P),range(P),range(2),range(P)))
INDEX={s:i for i,s in enumerate(STATES)}
TRAIN=tuple(s for s in STATES if s[0]%2==0)


def value(e,s):
    op=e[0]
    if op=='field':return s[e[1]]
    if op=='constant':return e[1]
    if op=='difference':return (value(e[1],s)-value(e[2],s))%P
    if op=='equals':return value(e[1],s)==value(e[2],s)
    if op=='less':return value(e[1],s)<value(e[2],s)
    raise ValueError('unknown primitive')


def complexity(e):return 1+sum(complexity(x) for x in e[1:] if isinstance(x,tuple))

def expression(e):
    if e[0]=='field':return FIELDS[e[1]]
    if e[0]=='constant':return str(e[1])
    a,b=expression(e[1]),expression(e[2])
    return f'(({a}-{b})%7)' if e[0]=='difference' else f'({a}{"==" if e[0]=="equals" else "<"}{b})'


def primitives():
    f=[('field',i) for i in (0,1,3)]
    quantities=f+[('difference',f[0],f[1]),('difference',f[1],f[0])]
    atoms=[(op,a,('constant',c)) for a in quantities for c in range(P) for op in ('equals','less')]
    atoms += [(op,a,b) for a,b in product(f,f) if a!=b for op in ('equals','less')]
    atoms += [('equals',('field',2),('constant',0))]
    kept={};allbits=(1<<len(STATES))-1
    for e in sorted(atoms,key=lambda e:(complexity(e),expression(e))):
        mask=sum(int(value(e,s))<<i for i,s in enumerate(STATES))
        if mask in (0,allbits):continue
        kept.setdefault(min(mask,allbits^mask),(e,mask))
    return tuple(kept.values())
ATOMS=primitives()


def predict(t,s):
    if t is None:return None
    while t[0]=='if':t=t[2] if value(t[1],s) else t[3]
    return t[1]

def size(t):return 1 if t[0]=='gain' else 1+complexity(t[1])+size(t[2])+size(t[3])

def splits(t):return 0 if t is None or t[0]=='gain' else 1+splits(t[2])+splits(t[3])

def show(t):
    if t is None:return 'unknown'
    if t[0]=='gain':return str(t[1])
    return f'({show(t[2])} if {expression(t[1])} else {show(t[3])})'

def compile_tree(t):
    src='def forward(position,other,object,last,command):\n    return ('+show(t)+' * command) % 7\n'
    ns={'__builtins__':{}};exec(compile(src,'<evidence_tree>','exec'),ns)
    fn=ns['forward'];fn.source=src;return fn


def infer(samples,charge,depth=3,width=6):
    if not samples:return []
    dedup={}
    for s,g in samples:
        s=tuple(s)
        if s in dedup and dedup[s]!=g:return []
        dedup[s]=g
    rows=list(dedup.items());n=len(rows)
    gains={g:sum(int(y==g)<<i for i,(s,y) in enumerate(rows)) for g in set(dedup.values())}
    pm=[]
    for e,mask in ATOMS:
        charge('ops',n)
        pm.append((e,sum(((mask>>INDEX[s])&1)<<i for i,(s,y) in enumerate(rows))))
    @lru_cache(None)
    def grow(mask,d):
        labs=[g for g,m in gains.items() if mask&m]
        if len(labs)==1:return (('gain',labs[0]),)
        if d==0:return ()
        options=[]
        for e,m in pm:
            charge('ops',1);l=mask&m;r=mask^l
            if not l or not r:continue
            lc,rc=l.bit_count(),r.bit_count()
            merit=sum((l&v).bit_count()**2/lc+(r&v).bit_count()**2/rc for v in gains.values())
            options.append((-merit,complexity(e),expression(e),e,l,r))
        options.sort(key=lambda row:row[:3]);trees=[]
        for _,_,_,e,l,r in options[:12 if d==depth else 8]:
            for a,b in product(grow(l,d-1)[:2],grow(r,d-1)[:2]):trees.append(('if',e,a,b))
        trees=sorted(set(trees),key=lambda t:(size(t),repr(t)))
        return tuple(t for t in trees if size(t)<=size(trees[0])+10)[:width] if trees else ()
    return list(grow((1<<n)-1,depth))


def choose(models,order,seen,charge):
    best=None;bestkey=None
    for s in order:
        if s in seen:continue
        predictions=[predict(t,s) for t in models];charge('ops',max(1,len(models)))
        c=Counter(predictions);disagree=len(models)**2-sum(n*n for n in c.values())
        leaf_count=sum(1 for x in seen if models and predict(models[0],x)==predict(models[0],s))
        novelty=min((sum(a!=b for a,b in zip(s,x)) for x in seen),default=4)
        key=(disagree,-leaf_count,novelty)
        if bestkey is None or key>bestkey:best,bestkey=s,key
    return best,{'disagreement':bestkey[0] if bestkey else 0,'leaf_count':-bestkey[1] if bestkey else 0}
