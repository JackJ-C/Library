"""只接输入输出。高层算子可学习；底层语言与构造器不是学习出来的。"""
from dataclasses import dataclass
from hashlib import sha256
from itertools import permutations
import json


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(obj):
    return sha256(canonical(obj).encode()).hexdigest()


def tuple_tree(obj):
    return tuple(tuple_tree(v) for v in obj) if isinstance(obj, (list, tuple)) else obj


def nodes(expr):
    if expr[0] in ('x', 'c'): return 1
    if expr[0] == 'call': return 1 + nodes(expr[2])
    return 1 + sum(nodes(a) for a in expr[1:])


def substitute(body, arg):
    if body[0] == 'x': return arg
    if body[0] == 'c': return body
    return (body[0],) + tuple(substitute(a, arg) for a in body[1:])


def expand(expr, macros):
    if expr[0] == 'call':
        return substitute(macros[expr[1]], expand(expr[2], macros))
    if expr[0] in ('x', 'c'): return expr
    return (expr[0],) + tuple(expand(a, macros) for a in expr[1:])


def source(expr):
    op = expr[0]
    if op == 'x': return 'x'
    if op == 'c':
        if type(expr[1]) is not int: raise ValueError('integer literal required')
        return str(expr[1])
    a = source(expr[1])
    if op == 'abs': return 'abs(' + a + ')'
    if op == 'half': return '(' + a + '//2)'
    if op == 'parity': return '(' + a + '%2)'
    b = source(expr[2])
    if op == 'eq': return 'int(' + a + '==' + b + ')'
    signs = {'add': '+', 'sub': '-', 'mul': '*'}
    if op not in signs: raise ValueError('unknown operator')
    return '(' + a + signs[op] + b + ')'


def evaluate(expr, x, counter=None):
    if counter is not None: counter.scalar_ops += 1
    op = expr[0]
    if op == 'x': return x
    if op == 'c': return expr[1]
    a = evaluate(expr[1], x, counter)
    if op == 'abs': return abs(a)
    if op == 'half': return a // 2
    if op == 'parity': return a % 2
    b = evaluate(expr[2], x, counter)
    if op == 'eq': return int(a == b)
    if op == 'add': return a + b
    if op == 'sub': return a - b
    if op == 'mul': return a * b
    raise ValueError('unknown operator')


def compile_program(expr, macros):
    lowered = expand(tuple_tree(expr), macros)
    text = 'def generated(x):\n    return ' + source(lowered) + '\n'
    scope = {'__builtins__': {}, 'abs': abs, 'int': int}
    exec(compile(text, '<Library-M21-generated>', 'exec'), scope)
    fn = scope['generated']
    fn.source, fn.expression, fn.lowered = text, expr, lowered
    fn.fingerprint = sha256(text.encode()).hexdigest()
    return fn


class OutOfFuel(Exception): pass
class Found(Exception):
    def __init__(self, expr): self.expr = expr


@dataclass
class Fuel:
    limit: int
    attempts: int = 0
    scalar_ops: int = 0

    def spend(self):
        if self.attempts >= self.limit: raise OutOfFuel()
        self.attempts += 1


def enumerate_seed(examples, fuel, maximum=9, constants=(-2,-1,0,1,2,3)):
    """每次证据变化重建样本等价类，不永远丢弃旧等价类的非代表。"""
    xs, wanted = tuple(x for x, _ in examples), tuple(y for _, y in examples)
    by_size = {n: [] for n in range(1, maximum+1)}
    seen = set()
    def add(expr, n, sig):
        fuel.spend()
        fuel.scalar_ops += len(sig)
        if sig == wanted: raise Found(expr)
        if sig not in seen:
            seen.add(sig)
            by_size[n].append((expr, sig, fuel.attempts))
    try:
        add(('x',), 1, xs)
        for c in constants: add(('c', c), 1, (c,)*len(xs))
        for n in range(2, maximum+1):
            for expr, sig, _ in by_size[n-1]:
                for op, out in (('abs', tuple(abs(x) for x in sig)),
                                ('half', tuple(x//2 for x in sig)),
                                ('parity', tuple(x%2 for x in sig))):
                    add((op, expr), n, out)
            for nl in range(1, n-1):
                for a, av, ai in by_size[nl]:
                    for b, bv, bi in by_size[n-1-nl]:
                        add(('sub', a, b), n, tuple(x-y for x,y in zip(av,bv)))
                        if ai <= bi:
                            add(('add', a, b), n, tuple(x+y for x,y in zip(av,bv)))
                            add(('mul', a, b), n, tuple(x*y for x,y in zip(av,bv)))
    except Found as found:
        return found.expr
    return None


def affine_arg(a, b):
    result = ('x',) if a == 1 else ('mul', ('c', a), ('x',))
    return result if b == 0 else ('add', result, ('c', b))


def macro_branch(name, body, examples, fuel):
    """公共组合规则不含目标名；抽象体由先前程序提供。"""
    for a in (-3,-2,-1,1,2,3):
        for b in range(-4,5):
            values = [evaluate(body, a*x+b, fuel) for x,_ in examples]
            for d in range(-4,5):
                fuel.spend()
                fuel.scalar_ops += len(values)
                if all(v+d == y for v,(_,y) in zip(values,examples)):
                    call = ('call', name, affine_arg(a,b))
                    return call if d == 0 else ('add', call, ('c',d))
    return None


def fit(examples, macros=None, order=(), budget=200000, maximum=9, constants=(-2,-1,0,1,2,3)):
    if type(budget) is not int or budget < 1: raise ValueError('positive finite budget')
    if type(maximum) is not int or maximum < 1: raise ValueError('positive node bound')
    if not constants or any(type(c) is not int for c in constants): raise ValueError('integer constants')
    points={}
    for x,y in examples:
        if type(x) is not int or type(y) is not int: raise ValueError('integer examples required')
        if x in points and points[x] != y: return {'status':'inconsistent','expression':None,'attempts':0,'scalar_ops':0}
        points[x]=y
    if not points: return {'status':'insufficient_evidence','expression':None,'attempts':0,'scalar_ops':0}
    examples=tuple(points.items()); macros={} if macros is None else macros
    if len(set(order)) != len(order) or set(order)!=set(macros): raise ValueError('plan must preserve every macro branch')
    fuel=Fuel(budget); route='seed'; expr=None
    trace=[]
    try:
        before=fuel.attempts
        expr=enumerate_seed(examples,fuel,min(3,maximum),constants) if macros else None
        if macros: trace.append({'branch':'seed-small','attempts':fuel.attempts-before,'fit':expr is not None})
        if expr is None:
            for name in order:
                before=fuel.attempts
                expr=macro_branch(name,macros[name],examples,fuel)
                trace.append({'branch':name,'attempts':fuel.attempts-before,'fit':expr is not None})
                if expr is not None:
                    route=name
                    break
        if expr is None:
            before=fuel.attempts
            expr=enumerate_seed(examples,fuel,maximum,constants)
            trace.append({'branch':'seed','attempts':fuel.attempts-before,'fit':expr is not None})
        status='fit' if expr is not None else 'node_bound_exhausted'
    except OutOfFuel:
        status='budget_exhausted'
    return {'status':status,'expression':expr,'route':route,'attempts':fuel.attempts,
            'scalar_ops':fuel.scalar_ops,'route_trace':trace,
            'evidence_key':digest(examples),'grammar_key':digest(macros),'plan':list(order)}


def subterms(expr):
    yield expr
    if expr[0] not in ('c','x'):
        for child in expr[1:]: yield from subterms(child)


def learn_macros(program_records, maximum=6):
    supports={}
    for idx,row in enumerate(program_records):
        if not row['accepted']: continue
        expr=tuple_tree(row['expression'])
        for term in set(subterms(expr)):
            size=nodes(term)
            if 3<=size<=7 and any(t[0]=='x' for t in subterms(term)):
                supports.setdefault(term,set()).add(idx)
    ranked=sorted(((len(ids)*(nodes(term)-2),len(ids),canonical(term),term,sorted(ids))
                   for term,ids in supports.items() if len(ids)>=2),reverse=True)
    selected=ranked[:maximum]
    rows=[]; macros={}
    for i,(score,support,_,body,ids) in enumerate(selected):
        name='op_'+str(i)
        macros[name]=body
        rows.append({'name':name,'body':body,'definition':source(body),'support':support,
                     'source_task_indices':ids,'compression_score':score,'expanded_nodes':nodes(body)})
    return macros,rows


def learn_plan(profile_rows, names):
    """有限调度程序归纳：仅依据先导候选成功/成本，不读任务名字。"""
    best=None; checked=0
    for order in permutations(names):
        solved=0; total=0
        for row in profile_rows:
            for name in order:
                total+=row[name]['attempts']
                if row[name]['fit']:
                    solved+=1
                    break
        key=(-solved,total,order)
        if best is None or key<best: best=key
        checked+=1
    if best is None: best=(0,0,())
    return {'order':list(best[2]),'pilot_solved':-best[0],'pilot_candidate_cost':best[1],
            'plans_examined':checked}


def compile_plan(order):
    """生成并实际绑定搜索调度函数。可组合原语与编译器仍固定。"""
    order=tuple(order)
    if any(not isinstance(v,str) or not v.startswith('op_') or not v[3:].isdigit() for v in order):
        raise ValueError('unknown plan token')
    text='def search(examples, macros, budget=200000):\n    return fit(examples, macros, '+repr(order)+', budget=budget)\n'
    scope={'__builtins__':{},'fit':fit}
    exec(compile(text,'<Library-M23-generated-plan>','exec'),scope)
    fn=scope['search']; fn.source=text; fn.fingerprint=sha256(text.encode()).hexdigest()
    return fn


def learn_normalized_macros(program_records, observed_domain, maximum=6):
    """给定的第二种抽象构造器：消除输出平移再按已见域归组。

    归组只是选择可执行代表，不证明组内程序全域等价；所有变体保留。
    """
    domain=tuple(observed_domain); buckets={}
    for idx,row in enumerate(program_records):
        if not row['accepted']: continue
        expr=tuple_tree(row['expression'])
        zero=evaluate(expr,0)
        normalized=expr if zero==0 else ('sub',expr,('c',zero))
        candidates=[(t,'subterm') for t in set(subterms(expr)) if 3<=nodes(t)<=7]
        candidates.append((normalized,'subtract_value_at_zero'))
        for body,kind in candidates:
            if not any(t[0]=='x' for t in subterms(body)): continue
            signature=tuple(evaluate(body,x) for x in domain)
            if len(set(signature))<2: continue
            bucket=buckets.setdefault(signature,{'sources':set(),'variants':{}})
            bucket['sources'].add(idx)
            bucket['variants'][body]=kind
    ranked=[]
    for signature,bucket in buckets.items():
        if len(bucket['sources'])<2: continue
        body=min(bucket['variants'],key=lambda t:(nodes(t),canonical(t)))
        if not 3<=nodes(body)<=7: continue
        score=len(bucket['sources'])*(nodes(body)-2)
        ranked.append((score,len(bucket['sources']),canonical(body),body,bucket,signature))
    ranked.sort(key=lambda r:r[:3],reverse=True)
    macros={};rows=[]
    for i,(score,support,_,body,bucket,sig) in enumerate(ranked[:maximum]):
        name='op_'+str(i);macros[name]=body
        variants=[{'body':v,'construction':bucket['variants'][v]} for v in sorted(bucket['variants'],key=canonical)]
        rows.append({'name':name,'body':body,'definition':source(body),'support':support,
            'source_task_indices':sorted(bucket['sources']),'compression_score':score,
            'expanded_nodes':nodes(body),'retained_variants':variants,
            'selection_scope':list(domain),'sample_signature':list(sig),
            'global_equivalence_proved':False})
    return macros,rows
