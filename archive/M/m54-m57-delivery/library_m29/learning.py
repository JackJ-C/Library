"""Finite synthesis and three-generation handoff. The CEGIS coordinator is fixed."""
from random import Random
from .runtime import (LEAVES,BRANCHES,run_find,run_flatmap,nodes,readable,digest,
                      FuelExhausted,SemanticError,tree)
from .proof import prove

SEED_ENABLED=True


def seed_candidates(kind,maximum=9):
    if not SEED_ENABLED:raise RuntimeError('handwritten seed expansion disabled')
    bank={1:[(x,) for x in LEAVES[kind]]};yield from bank[1]
    for n in range(3,maximum+1,2):
        row=[]
        for op in BRANCHES[kind]:
            for l in range(1,n-1,2):
                for a in bank[l]:
                    for b in bank[n-1-l]:row.append((op,a,b))
        bank[n]=row;yield from row


class GeneratedEngine:
    def __init__(self,finder,expander):
        self.finder,self.expander=tree(finder),tree(expander)
        if not prove(self.finder,'find')['passed'] or not prove(self.expander,'flatmap')['passed']:
            raise SemanticError('kernel lacks induction certificate')
        self._certified=(self.finder,self.expander)
        self.metrics=dict(find_calls=0,find_vm_steps=0,predicate_calls=0,
                          expand_calls=0,expand_vm_steps=0,mapper_calls=0)
    def valid(self):return self._certified==(self.finder,self.expander)
    def _check(self):
        if not self.valid():raise SemanticError('kernel binding changed; certificate revoked')
    def expand(self,values,mapper):
        self._check()
        out,m=run_flatmap(self.expander,values,mapper,limit=10000000)
        self.metrics['expand_calls']+=1;self.metrics['expand_vm_steps']+=m.steps
        self.metrics['mapper_calls']+=m.mappings
        return out
    def first(self,values,predicate):
        self._check()
        observed=[]
        def track(item):
            hit=predicate(item);observed.append((item,hit));return hit
        i,m=run_find(self.finder,values,track,limit=10000000)
        self.metrics['find_calls']+=1;self.metrics['find_vm_steps']+=m.steps
        self.metrics['predicate_calls']+=m.predicates
        if i is None:return None
        if i!=len(observed)-1 or observed[-1][1] is not True:
            raise SemanticError('untested or rejected candidate returned')
        return observed[-1][0]
    def candidates(self,kind,maximum=9):
        bank={1:[(x,) for x in LEAVES[kind]]};yield from bank[1]
        for n in range(3,maximum+1,2):
            jobs=[(op,l) for op in BRANCHES[kind] for l in range(1,n-1,2)]
            def perform(job):
                op,l=job
                return self.expand(bank[l],lambda a:self.expand(bank[n-1-l],lambda b:((op,a,b),)))
            row=self.expand(jobs,perform);bank[n]=row;yield from row


def cases(kind,lengths,seeds=range(8)):
    rows=[]
    for n in lengths:
        if kind=='find':rows.extend({'n':n,'mask':mask} for mask in range(1<<n))
        else:
            for seed in seeds:
                rng=Random(1907*seed+n)
                xs=[rng.randrange(-4,5) for _ in range(n)]
                mapping={str(i):[rng.randrange(-9,10) for _ in range(rng.randrange(4))] for i in range(-4,5)}
                rows.append({'xs':xs,'mapping':mapping})
    return rows


def failure(p,c,kind):
    try:
        if kind=='find':
            n,mask=c['n'],c['mask']
            actual,_=run_find(p,range(n),lambda i:bool(mask&(1<<i)),20*(n+1)*nodes(p))
            expected=next((i for i in range(n) if mask&(1<<i)),None)
        else:
            xs,mapping=c['xs'],c['mapping']
            actual,_=run_flatmap(p,xs,lambda i:mapping[str(i)],30*(len(xs)+1)*nodes(p))
            expected=tuple(y for x in xs for y in mapping[str(x)])
        if actual!=expected:return {'actual':actual,'expected':expected,'case':c}
    except (SemanticError,FuelExhausted,RecursionError) as e:return {'error':type(e).__name__,'case':c}
    return None


def discover(kind,engine=None,budget=50000):
    if engine is None and not SEED_ENABLED:raise RuntimeError('handwritten seed finder disabled')
    training=cases(kind,range(5));active=[0];rounds=[];attempts=0
    class Budget(Exception):pass
    for _ in range(16):
        def good(p):
            nonlocal attempts
            if attempts>=budget:raise Budget()
            attempts+=1
            return all(failure(p,training[i],kind) is None for i in active)
        factory=lambda:seed_candidates(kind) if engine is None else engine.candidates(kind)
        try:
            selected=next((p for p in factory() if good(p)),None) if engine is None else engine.first(factory(),good)
        except Budget:return {'status':'budget_exhausted','attempts':attempts,'rounds':rounds}
        if selected is None:return {'status':'grammar_exhausted','attempts':attempts,'rounds':rounds}
        bad=None
        for i,c in enumerate(training):
            w=failure(selected,c,kind)
            if w is not None:bad=(i,w);break
        rounds.append({'program':selected,'readable':readable(selected,kind),'active_before':list(active),
                       'cumulative_attempts':attempts,'counterexample':None if bad is None else {'id':bad[0],'detail':bad[1]}})
        if bad is None:
            validation=cases(kind,range(5,8),range(100,108));errors=[i for i,c in enumerate(validation) if failure(selected,c,kind)]
            proof=prove(selected,kind)
            return {'status':'fit' if not errors and proof['passed'] else 'rejected','kind':kind,
                    'program':selected,'program_sha256':digest(selected),'attempts':attempts,'rounds':rounds,
                    'training_cases':len(training),'validation_cases':len(validation),'validation_failures':errors,
                    'proof':proof,'origin':'seed' if engine is None else 'generated_search_and_expansion'}
        if bad[0] in active:raise RuntimeError('nonstationary checker')
        active.append(bad[0])
    return {'status':'round_limit','attempts':attempts,'rounds':rounds}


def bootstrap():return {kind:discover(kind) for kind in ('find','flatmap')}


def challenge(p,kind):
    rows=[]
    for seed in range(1000,1064):
        rng=Random(seed);n=rng.randrange(8,65)
        if kind=='find':c={'n':n,'mask':sum(int(rng.random()<.15)<<i for i in range(n))}
        else:
            xs=[rng.randrange(-20,21) for _ in range(n)]
            mapping={str(i):[rng.randrange(-100,101) for _ in range(rng.randrange(6))] for i in range(-20,21)}
            c={'xs':xs,'mapping':mapping}
        rows.append({'seed':seed,'case':c,'failure':failure(p,c,kind)})
    return rows
