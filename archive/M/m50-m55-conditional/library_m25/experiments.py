"""性质、黑箱任务和独立评估。真参数留在此层，不传给合成模块。"""
from collections import Counter
from fractions import Fraction
from random import Random
from .language import (candidate_factory, synthesize, evaluate, make_builder,
                       make_search, source, digest, tree)
from .algebra import prove_builder, prove_search


TRAIN_POINTS = (-2, -1, 0, 1, 2)
TRANSFER_POINTS = tuple(range(-16, 17))


def environment(f, x, previous=None):
    values = dict(x=x, fx=f(x), f0=f(0), f1=f(1))
    if previous is not None:
        t = previous(f)
        values.update(tx=t(x), t0=t(0), t1=t(1))
    return values


def property_cases(level, seeds, points, previous=None, scale=9):
    """只有性质与观测，没有正确构造器函数体或目标公式标签。"""
    cases = []
    for seed in seeds:
        rng = Random(seed)
        grid = sorted(set(points) | {0, 1})
        table = {x: rng.randint(-scale, scale) for x in grid}
        f = table.__getitem__
        a, b = rng.choice((-4, -2, 1, 3)), rng.choice((-7, -3, 2, 5))
        shifted = lambda x: f(x) + (a*x if level else 0) + b
        # 保持性样本通过直接把锚点设0产生，不用待发现公式归一化。
        normal = dict(table)
        normal[0] = 0
        if level: normal[1] = 0
        g = normal.__getitem__
        for x in points:
            cases.append(dict(seed=seed, kind='invariant', x=x,
                              left=environment(f, x, previous),
                              right=environment(shifted, x, previous)))
            cases.append(dict(seed=seed, kind='preserve', x=x,
                              left=environment(g, x, previous), expected=g(x)))
        for x in range(level+1):
            cases.append(dict(seed=seed, kind='anchor', x=x,
                              left=environment(f, x, previous), expected=0))
    return cases


def property_failure(expr, case):
    try:
        actual = evaluate(expr, case['left'])
        expected = evaluate(expr, case['right']) if 'right' in case else case['expected']
    except (ValueError, ZeroDivisionError, KeyError) as exc:
        return dict(kind='runtime_error', error=type(exc).__name__)
    if actual == expected: return None
    return dict(kind=case['kind'], x=case['x'], actual=str(actual), expected=str(expected),
                public_inputs=case)


def learn_builders():
    records, built, previous = [], [], None
    for level in range(2):
        cases = property_cases(level, range(8), TRAIN_POINTS, previous)
        names = ('x', 'fx', 'f0', 'f1') + (() if previous is None else ('tx', 't0', 't1'))
        result = synthesize(candidate_factory(names), tuple(range(len(cases))),
                            lambda expr, key: property_failure(expr, cases[key]))
        row = dict(level=level, training_cases=cases, **result)
        if result['status'] != 'fit':
            records.append(row)
            return records, built
        expr = result['expression']
        generated = make_builder(expr, previous)
        validation = property_cases(level, range(100, 108), TRAIN_POINTS, previous, scale=31)
        future = property_cases(level, range(1000, 1064), TRANSFER_POINTS, previous, scale=127)
        row.update(generated_source=generated.source, fingerprint=generated.fingerprint,
                   validation_cases=len(validation),
                   validation_failures=[i for i,c in enumerate(validation) if property_failure(expr,c)],
                   challenge_cases=len(future),
                   challenge_failures=[i for i,c in enumerate(future) if property_failure(expr,c)],
                   algebra=prove_builder(expr, level, built[0].expression if level else None),
                   degenerate_zero_rejected=any(property_failure(('c',0),c) for c in cases))
        row['accepted'] = (not row['validation_failures'] and row['algebra']['passed'])
        records.append(row)
        if not row['accepted']: return records, built
        built.append(generated)
        previous = generated
    return records, built


def search_case(seed):
    rng = Random(seed)
    slope = rng.choice((-7, -5, -3, -1, 1, 2, 4, 6))
    root = rng.randint(-9, 9)
    p0, p1 = rng.sample([x for x in range(-12,13) if x != root], 2)
    registers = dict(p0=p0, p1=p1, r0=slope*(p0-root), r1=slope*(p1-root))
    return dict(seed=seed, registers=registers, slope=slope, root=root)


def search_failure(expr, case):
    # 检查器实际执行候选查询；根和斜率未传入候选执行环境。
    try:
        q = evaluate(expr, case['registers'])
        q = Fraction(q)
    except (ValueError, ZeroDivisionError, KeyError):
        return dict(kind='invalid_query', observations=case['registers'])
    if q.denominator != 1:
        return dict(kind='noninteger_query', proposed=str(q), observations=case['registers'])
    residual = case['slope'] * (int(q)-case['root'])
    if residual == 0: return None
    return dict(kind='nonzero_residual', proposed=int(q), residual=residual,
                observations=case['registers'])


def learn_search():
    cases = [search_case(i) for i in range(12)]
    result = synthesize(candidate_factory(('p0','p1','r0','r1'), rational=True),
                        tuple(range(12)), lambda e,i:search_failure(e,cases[i]))
    result['training_cases'] = cases
    if result['status'] != 'fit': return result, None
    generated = make_search(result['expression'])
    validation = [search_case(i) for i in range(100,132)]
    result.update(generated_source=generated.source, fingerprint=generated.fingerprint,
                  validation_cases=validation,
                  validation_failures=[i for i,c in enumerate(validation)
                                       if search_failure(result['expression'],c)],
                  algebra=prove_search(result['expression']))
    result['accepted'] = not result['validation_failures'] and result['algebra']['passed']
    return result, generated if result['accepted'] else None


def strong_reference_builder(f):
    # 仅独立评估对照，禁止合成器导入本函数。
    z, o = f(0), f(1)
    return lambda x: f(x)-z-x*(o-z)


def strong_reference_search(p0,p1,r0,r1):
    return Fraction(p0*r1-p1*r0, r1-r0)


def task(seed, family):
    rng = Random(seed*19+family)
    shift = rng.randint(-5,5)
    if family == 0: base=lambda x:(x-shift)**3
    elif family == 1: base=lambda x:(x-shift)**4
    elif family == 2: base=lambda x:abs(x-shift)+x*x
    else: base=lambda x:((x-shift)//3)+(x%2)+x*x*x
    drift, bias = rng.choice((-19,-11,7,13)), rng.choice((-101,-73,59,113))
    raw = lambda x:base(x)+drift*x+bias
    canonical_base = strong_reference_builder(base)
    coefficient = rng.choice([x for x in range(-31,32) if x])
    offset, linear = rng.randint(-100,100),rng.randint(-27,27)
    target = lambda x:coefficient*canonical_base(x)+offset+linear*x
    return raw,target,dict(seed=seed,family=family,shift=shift,coefficient=coefficient,
                           offset=offset,linear=linear,drift=drift,bias=bias)


class Queen:
    """可变的是构造/提案函数本体；安装、规范及测量框架保持可信。"""
    def __init__(self, builder, search):
        self.builder, self.search = builder, search
        self.program = lambda x: 0
        self.trace = []
        self.certificate = None
        self.context = None
        self._approved_bindings = None

    def valid(self):
        return (self.context is not None and self.certificate == digest(self.context)
                and self._approved_bindings == (self.builder,self.search,self.program))

    def decide(self, x): return self.program(x)

    def fit(self, raw, get_value, mode='generated', task_id='task'):
        self.certificate, self.context, self._approved_bindings = None, None, None
        observations = {}
        def observe(x):
            if x not in observations: observations[x]=get_value(x)
            return observations[x]
        tool = self.builder(raw)
        y0,y1 = observe(0),observe(1)
        diagnostic = next((x for x in (2,3,4,-1,-2) if tool(x) != 0),None)
        if diagnostic is None: return dict(accepted=False,status='no_nonzero_tool')
        query_log=[]
        def run(k):
            residual=k*tool(diagnostic)+y0+diagnostic*(y1-y0)-observe(diagnostic)
            query_log.append([k,residual])
            return residual
        p0,p1=-31,31
        r0,r1=run(p0),run(p1)
        chosen=None
        if r0==0: chosen=p0
        elif r1==0: chosen=p1
        elif mode in ('generated','reference'):
            try: proposed=Fraction(self.search(p0,p1,r0,r1))
            except (ValueError,ZeroDivisionError): proposed=None
            if proposed is not None and proposed.denominator==1 and -31<=proposed<=31:
                p=int(proposed)
                if run(p)==0: chosen=p
        elif mode=='enumeration':
            for p in range(-30,31):
                if run(p)==0:
                    chosen=p
                    break
        elif mode=='bisection':
            lo,hi,flo,fhi=p0,p1,r0,r1
            while hi-lo>1:
                mid=(lo+hi)//2
                fm=run(mid)
                if fm==0:
                    chosen=mid
                    break
                if (fm>0)==(flo>0):lo,flo=mid,fm
                else:hi,fhi=mid,fm
        elif mode!='none': raise ValueError('unknown mode')
        old=self.program
        generated=None
        validation=[]
        if chosen is not None:
            # 固定重组器由两个锚点恢复仿射部分，非学习内容。
            generated=lambda x:chosen*tool(x)+y0+x*(y1-y0)
            for x in (-3,5,8):
                validation.append([x,generated(x),observe(x)])
        accepted=generated is not None and all(a==b for _,a,b in validation)
        if accepted:self.program=generated
        self.trace.append(dict(task=task_id,queries=query_log,observations=sorted(observations.items()),
                               validation=validation,accepted=accepted))
        if accepted:
            self.context = dict(task=task_id, evidence=digest(self.trace[-1]),
                                builder=getattr(self.builder,'fingerprint','reference-builder'),
                                search=getattr(self.search,'fingerprint','reference-search'),
                                mode=mode, semantics='exact-v1')
            self.certificate = digest(self.context)
            self._approved_bindings = (self.builder,self.search,self.program)
        return dict(accepted=accepted,status='adopted' if accepted else 'rejected',
                    proposed=chosen,parameter_queries=len(query_log),query_trace=query_log,
                    measured_points=sorted(observations),measurements=sorted(observations.items()),
                    validation=validation,certificate=self.certificate,context=self.context,
                    binding_changed=self.program is not old)


def transfer(builders, search):
    rows,summary=[],{}
    if len(builders)!=2 or search is None:return rows,summary
    identity=lambda f:f
    variants=(('full',builders[1],search,'generated'),
              ('no_builder',identity,search,'generated'),
              ('no_search',builders[1],search,'enumeration'),
              ('neither',identity,search,'enumeration'),
              ('bisection',builders[1],search,'bisection'),
              ('zero_new_search',builders[1],search,'none'),
              ('handwritten',strong_reference_builder,strong_reference_search,'reference'),
              ('plain_json',builders[1],search,'generated'))
    for name,builder,law,mode in variants:
        counts=Counter()
        for seed in range(1000,1064):
            for family in range(4):
                raw,fn,metadata=task(seed,family)
                queen=Queen(builder,law)
                instance=id(queen)
                # JSON对照传递同一组测量值，不增加信息或改变算法。
                if name=='plain_json':
                    import json
                    oracle=lambda x:json.loads(json.dumps(fn(x)))
                else:oracle=fn
                result=queen.fit(raw,oracle,mode,task_id=str((seed,family)))
                future=[x for x in TRANSFER_POINTS if x not in result.get('measured_points',[])]
                actual=[queen.decide(x) for x in future] if result['accepted'] else []
                expected=[fn(x) for x in future]
                correct=sum(a==b for a,b in zip(actual,expected))
                # 正常旧程序为0；有任何旧成功退化都显式记录。
                regressions=sum(b==0 and a!=b for a,b in zip(actual,expected))
                counts['tasks']+=1;counts['accepted']+=result['accepted']
                counts['all_future_correct']+=result['accepted'] and correct==len(future)
                counts['future_cases']+=len(future);counts['future_correct']+=correct
                counts['parameter_queries']+=result.get('parameter_queries',0)
                counts['oracle_points']+=len(result.get('measured_points',[]))
                counts['regressions']+=regressions
                rows.append(dict(variant=name,metadata=metadata,**result,future_x=future,
                                 actual=actual,expected=expected,correct=correct,
                                 regressions=regressions,instance_preserved=id(queen)==instance))
        summary[name]=dict(counts)
    return rows,summary


def context_valid(certificate, context):
    return certificate == digest(context)


def stress(builders, search):
    if len(builders)!=2 or search is None:return {'not_executed':True}
    # 非线性及旧残差：真实测量确认后才能采用，不能单凭提案值发证。
    nonlinear=[]
    for fn in (lambda p:p*p-9,lambda p:p*p-16):
        p0,p1=0,5;r0,r1=fn(p0),fn(p1)
        q=Fraction(search(p0,p1,r0,r1));value=fn(q)
        nonlinear.append(dict(proposed=str(q),actual_residual=str(value),accepted=value==0))
    stale_proposal=Fraction(search(0,1,-2,-1))
    stale_residual=stale_proposal-7
    context=dict(task='t',evidence='e',builder=builders[1].fingerprint,search=search.fingerprint,semantics='exact-v1')
    cert=digest(context)
    invalid=[]
    for key in context:
        changed=dict(context);changed[key]+='-changed'
        invalid.append(dict(changed=key,accepted=context_valid(cert,changed)))
    raw=lambda x:x*x
    base=lambda x:3*x*(x-1)+2*x+5
    latent=lambda x:base(x)+int(x==13)
    q=Queen(builders[1],search);result=q.fit(raw,latent)
    errors=[x for x in TRANSFER_POINTS if q.decide(x)!=latent(x)] if result['accepted'] else []
    wrong=Queen(builders[1],search);wr=wrong.fit(raw,base)
    wrong_errors=[x for x in TRANSFER_POINTS if wrong.decide(x)!=base(x)+1] if wr['accepted'] else []
    limited=synthesize(candidate_factory(('x','fx','f0','f1')),(0,),lambda e,i:{'reject':True},budget=1)
    return dict(nonlinear=nonlinear,stale_proposal=str(stale_proposal),stale_residual=str(stale_residual),
                stale_accepted=stale_residual==0,context_attacks=invalid,
                fresh_context_accepted=context_valid(cert,context),
                latent_accepted=result['accepted'],latent_errors=errors,
                wrong_reference_accepted=wr['accepted'],wrong_reference_errors=wrong_errors,
                resource_status=limited['status'],
                missing_history_status='insufficient_history' if search_failure(search.expression, {'registers':{}}) else 'unexpected',
                one_observation_ambiguity={'p':0,'residuals':[-2,-2],'possible_roots':[2,1]},
                corrupted_semantics={'declared_algebra_passes':prove_search(search.expression)['passed'],
                                     'correct_proposal':str(search(0,1,-2,-1)),
                                     'faulty_division_add_one_residual':str(search(0,1,-2,-1)+1-2)},
                trusted_layers=['enumerator','property contracts','arithmetic interpreter','installer','task reference'])


def study():
    builder_rows,builders=learn_builders()
    search_row,law=learn_search()
    frozen=digest(dict(builders=[b.expression for b in builders],search=law.expression if law else None))
    rows,counts=transfer(builders,law)
    after=digest(dict(builders=[b.expression for b in builders],search=law.expression if law else None))
    negatives=stress(builders,law)
    return dict(builders=builder_rows,search=search_row,frozen_metaprograms=frozen,
                learning_unchanged_after_transfer=frozen==after,transfer_rows=rows,
                transfer_summary=counts,stress=negatives,
                scope='generated higher-order bodies and affine-feedback query law; fixed outer synthesizer')
