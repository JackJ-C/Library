"""Bridge to M25 without calling its handwritten finder or candidate factory.
Grammar construction and counterexample coordination remain supplied code.
"""
from .runtime import nodes
from library_m25 import language as lang
from library_m25 import experiments as exp


def candidate_factory(engine,names,rational=False):
    variables=tuple(('v',n) for n in names)
    products=engine.expand(range(len(variables)),lambda i:
             engine.expand(variables[i:],lambda b:(('*',variables[i],b),)))
    terms=(('c',1),)+variables+products
    singles=engine.expand(terms,lambda a:(a,('-',('c',0),a)))
    pairs=engine.expand(range(len(terms)),lambda i:engine.expand(terms[i+1:],
          lambda b:(('+',terms[i],b),('-',terms[i],b),('-',b,terms[i]))))
    bank=tuple(sorted({('c',0),*singles,*pairs},key=lambda e:(lang.size(e),lang.source(e))))
    def factory():
        yield from bank
        if rational:
            # Streaming one denominator block at a time; no hidden oracle labels.
            for d in bank:
                if d not in (('c',0),('c',1)):
                    yield from engine.expand(bank,lambda n:(('/',n,d),))
    return factory


def synthesize(engine,factory,case_ids,check,budget=1000000,max_rounds=16):
    if not case_ids or type(budget)is not int or budget<=0:raise ValueError('finite task required')
    active=[case_ids[0]];log=[];attempts=0;checks=0
    class Budget(Exception):pass
    for _ in range(max_rounds):
        before=attempts
        def good(expr):
            nonlocal attempts,checks
            if attempts>=budget:raise Budget()
            attempts+=1
            for i in active:
                checks+=1
                if check(expr,i) is not None:return False
            return True
        try:found=engine.first(factory(),good)
        except Budget:return dict(status='budget_exhausted',expression=None,rounds=log,attempts=attempts,checks=checks,active=active)
        if found is None:return dict(status='grammar_exhausted',expression=None,rounds=log,attempts=attempts,checks=checks,active=active)
        failure=None
        for i in case_ids:
            checks+=1;witness=check(found,i)
            if witness is not None:failure={'id':i,'witness':witness};break
        log.append(dict(expression=found,source=lang.source(found),nodes=lang.size(found),
            attempted_this_round=attempts-before,cumulative_attempts=attempts,
            active_before=list(active),counterexample=failure))
        if failure is None:return dict(status='fit',expression=found,rounds=log,attempts=attempts,checks=checks,active=active)
        if failure['id'] in active:raise RuntimeError('nonstationary checker')
        active.append(failure['id'])
    return dict(status='round_limit',expression=None,rounds=log,attempts=attempts,checks=checks,active=active)


def run_bridge(engine):
    originals=(exp.synthesize,exp.candidate_factory,lang.synthesize,lang.candidate_factory)
    def forbidden(*args,**kwargs):raise RuntimeError('old M25 discovery path disabled')
    try:
        exp.synthesize=lambda factory,ids,check,**kw:synthesize(engine,factory,ids,check,**kw)
        exp.candidate_factory=lambda names,rational=False:candidate_factory(engine,names,rational)
        lang.synthesize=lang.candidate_factory=forbidden
        builders,built=exp.learn_builders();search,law=exp.learn_search()
        before=lang.digest({'builders':[f.expression for f in built],'search':law.expression})
        rows,summary=exp.transfer(built,law)
        after=lang.digest({'builders':[f.expression for f in built],'search':law.expression})
        return dict(builders=builders,search=search,transfer_rows=rows,transfer_summary=summary,
                    old_discovery_disabled=True,engine_metrics=dict(engine.metrics),
                    frozen_metaprograms=before,learning_unchanged_after_transfer=before==after)
    finally:
        exp.synthesize,exp.candidate_factory,lang.synthesize,lang.candidate_factory=originals


class GatedQueen(exp.Queen):
    """Opt-in execution guard. Historical Queen/runners are intentionally unchanged."""
    def decide(self,x):
        if not self.valid():
            raise RuntimeError('execution denied: missing or obsolete certificate')
        return super().decide(x)
