"""通用算术元程序语言。这里没有归一化、插值或正确答案模板。"""
from fractions import Fraction
from hashlib import sha256
from itertools import combinations_with_replacement
import json


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def tree(value):
    return tuple(tree(v) for v in value) if isinstance(value, (list, tuple)) else value


def size(expr):
    return 1 if expr[0] in ('v', 'c') else 1 + sum(size(x) for x in expr[1:])


def source(expr, bindings=None):
    bindings = {} if bindings is None else bindings
    op = expr[0]
    if op == 'v':
        name = expr[1]
        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError('invalid variable name')
        return bindings.get(name, name)
    if op == 'c':
        if type(expr[1]) is not int:
            raise ValueError('integer constant required')
        return str(expr[1])
    signs = {'+': '+', '-': '-', '*': '*'}
    if op == '/':
        return 'Fraction(' + source(expr[1], bindings) + ',' + source(expr[2], bindings) + ')'
    if op not in signs or len(expr) != 3:
        raise ValueError('invalid expression')
    return '(' + source(expr[1], bindings) + signs[op] + source(expr[2], bindings) + ')'


def evaluate(expr, values):
    op = expr[0]
    if op == 'v': return values[expr[1]]
    if op == 'c': return expr[1]
    a, b = evaluate(expr[1], values), evaluate(expr[2], values)
    if op == '+': return a + b
    if op == '-': return a - b
    if op == '*': return a * b
    if op == '/': return Fraction(a, b)
    raise ValueError('invalid operation')


def polynomial_bank(names):
    """枚举0/1、原始变量、二次单项式及最多两个带符号项。"""
    variables = [('v', name) for name in names]
    terms = [('c', 1)] + variables
    terms += [('*', a, b) for a, b in combinations_with_replacement(variables, 2)]
    expressions = {('c', 0)}
    for a in terms:
        expressions.add(a)
        expressions.add(('-', ('c', 0), a))
    for i, a in enumerate(terms):
        for b in terms[i + 1:]:
            expressions.add(('+', a, b))
            expressions.add(('-', a, b))
            expressions.add(('-', b, a))
    return tuple(sorted(expressions, key=lambda e: (size(e), source(e))))


def candidate_factory(names, rational=False):
    bank = polynomial_bank(names)
    def candidates():
        yield from bank
        if rational:
            # 分母按大小、源码枚举；不是一个预置的搜索公式表。
            for denominator in bank:
                if denominator == ('c', 0) or denominator == ('c', 1):
                    continue
                for numerator in bank:
                    yield ('/', numerator, denominator)
    return candidates


def synthesize(factory, case_ids, check, budget=1000000, max_rounds=16):
    """只调用性质检查能力，接收反例ID；看不到目标源码或隐藏参数。"""
    if not case_ids or type(budget) is not int or budget <= 0:
        raise ValueError('finite nonempty experiment required')
    active, log, attempts, checks = [case_ids[0]], [], 0, 0
    for _ in range(max_rounds):
        found, before = None, attempts
        for expr in factory():
            if attempts >= budget:
                return dict(status='budget_exhausted', expression=None, rounds=log,
                            attempts=attempts, checks=checks, active=active)
            attempts += 1
            good = True
            for identifier in active:
                checks += 1
                if check(expr, identifier) is not None:
                    good = False
                    break
            if good:
                found = expr
                break
        if found is None:
            return dict(status='grammar_exhausted', expression=None, rounds=log,
                        attempts=attempts, checks=checks, active=active)
        failure = None
        for identifier in case_ids:
            checks += 1
            witness = check(found, identifier)
            if witness is not None:
                failure = {'id': identifier, 'witness': witness}
                break
        log.append(dict(expression=found, source=source(found), nodes=size(found),
                        attempted_this_round=attempts-before, cumulative_attempts=attempts,
                        active_before=list(active), counterexample=failure))
        if failure is None:
            return dict(status='fit', expression=found, rounds=log,
                        attempts=attempts, checks=checks, active=active)
        if failure['id'] in active:
            raise RuntimeError('nonstationary checker')
        active.append(failure['id'])
    return dict(status='round_limit', expression=None, rounds=log,
                attempts=attempts, checks=checks, active=active)


def make_builder(expr, previous=None):
    """编译运行时学得函数体：程序作为输入，新工具函数作为输出。"""
    expr = tree(expr)
    bindings = {'x': 'x', 'fx': 'f(x)', 'f0': 'f(0)', 'f1': 'f(1)'}
    if previous is not None:
        bindings.update(tx='prior(x)', t0='prior(0)', t1='prior(1)')
    # AST变量白名单，不能把拼接文本作为输入。
    def inspect(e):
        if e[0] == 'v' and e[1] not in bindings: raise ValueError('unbound register')
        if e[0] not in ('v', 'c'):
            for child in e[1:]: inspect(child)
    inspect(expr)
    text = 'def construct(f):\n'
    if previous is not None:
        text += '    prior = previous(f)\n'
    text += '    def tool(x):\n        return ' + source(expr, bindings) + '\n    return tool\n'
    scope = {'__builtins__': {}, 'previous': previous, 'Fraction': Fraction}
    exec(compile(text, '<Library-generated-builder>', 'exec'), scope)
    fn = scope['construct']
    fn.expression, fn.source = expr, text
    fn.fingerprint = digest({'source': text, 'previous': previous.fingerprint if previous else None})
    return fn


def make_search(expr):
    expr = tree(expr)
    def inspect(e):
        if e[0] == 'v' and e[1] not in ('p0','p1','r0','r1'):
            raise ValueError('unbound register')
        if e[0] not in ('v','c'):
            for child in e[1:]: inspect(child)
    inspect(expr)
    text = 'def propose(p0,p1,r0,r1):\n    return ' + source(expr) + '\n'
    scope = {'__builtins__': {}, 'Fraction': Fraction}
    exec(compile(text, '<Library-generated-search-law>', 'exec'), scope)
    fn = scope['propose']
    fn.expression, fn.source, fn.fingerprint = expr, text, sha256(text.encode()).hexdigest()
    return fn
