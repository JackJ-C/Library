"""递归整数语法的有界枚举。目标程序不可见；只收到输入输出。

语法无限，实际每次搜索受节点和候选预算限制。相同样本上的语义去重
是加速方法，不保证未见输入等价或表达式的唯一性。所有失败显式返回。
"""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from typing import Callable, Optional, Tuple

Expr = tuple
Examples = Tuple[Tuple[int, int], ...]


def source(expr: Expr) -> str:
    op = expr[0]
    if op == 'x':
        return 'x'
    if op == 'c':
        if type(expr[1]) is not int:
            raise ValueError('integer constant required')
        return repr(expr[1])
    if op == 'abs':
        return 'abs(' + source(expr[1]) + ')'
    if op == 'half':
        return '(' + source(expr[1]) + '//2)'
    if op == 'parity':
        return '(' + source(expr[1]) + '%2)'
    signs = {'add': '+', 'sub': '-', 'mul': '*'}
    if op not in signs:
        raise ValueError('unknown grammar operator')
    return '(' + source(expr[1]) + signs[op] + source(expr[2]) + ')'


def evaluate(expr: Expr, x: int) -> int:
    """独立树解释器，用来对照真实生成函数。"""
    op = expr[0]
    if op == 'x': return x
    if op == 'c': return expr[1]
    a = evaluate(expr[1], x)
    if op == 'abs': return abs(a)
    if op == 'half': return a // 2
    if op == 'parity': return a % 2
    b = evaluate(expr[2], x)
    if op == 'add': return a + b
    if op == 'sub': return a - b
    if op == 'mul': return a * b
    raise ValueError('unknown operator')


def compile_expr(expr: Expr) -> Callable[[int], int]:
    # 不接受任意源代码；仅由上面的封闭运算符递归生成。
    text = 'def generated(x):\n    return ' + source(expr) + '\n'
    scope = {'__builtins__': {}, 'abs': abs}
    exec(compile(text, '<library-generated-expression>', 'exec'), scope)
    fn = scope['generated']
    fn.source = text
    fn.fingerprint = sha256(text.encode()).hexdigest()
    fn.expression = expr
    return fn


@dataclass(frozen=True)
class Candidate:
    expression: Expr
    nodes: int
    attempt: int
    signature: tuple


@dataclass
class Catalogue:
    by_signature: dict
    attempts: int
    budget_hit: bool
    max_nodes: int


@lru_cache(maxsize=16)
def catalogue(xs: tuple, max_nodes: int = 9, budget: int = 200000) -> Catalogue:
    if not xs or any(type(x) is not int for x in xs):
        raise ValueError('nonempty integer inputs required')
    if type(max_nodes) is not int or max_nodes < 1 or type(budget) is not int or budget < 1:
        raise ValueError('positive search bounds required')
    by_sig, by_size = {}, {n: [] for n in range(1, max_nodes + 1)}
    attempts = 0

    def add(expr, size, sig):
        nonlocal attempts
        if attempts >= budget:
            raise StopIteration
        attempts += 1
        if sig not in by_sig:
            item = Candidate(expr, size, attempts, sig)
            by_sig[sig] = item
            by_size[size].append(item)

    try:
        add(('x',), 1, xs)
        for c in (-2, -1, 0, 1, 2, 3):
            add(('c', c), 1, (c,) * len(xs))
        for size in range(2, max_nodes + 1):
            for a in by_size[size - 1]:
                for op, sig in (
                    ('abs', tuple(abs(v) for v in a.signature)),
                    ('half', tuple(v // 2 for v in a.signature)),
                    ('parity', tuple(v % 2 for v in a.signature))):
                    add((op, a.expression), size, sig)
            for left_size in range(1, size - 1):
                right_size = size - 1 - left_size
                for a in by_size[left_size]:
                    for b in by_size[right_size]:
                        av, bv = a.signature, b.signature
                        add(('sub', a.expression, b.expression), size,
                            tuple(u - v for u, v in zip(av, bv)))
                        # 对交换律运算不重复两个次序。
                        if a.attempt <= b.attempt:
                            add(('add', a.expression, b.expression), size,
                                tuple(u + v for u, v in zip(av, bv)))
                            add(('mul', a.expression, b.expression), size,
                                tuple(u * v for u, v in zip(av, bv)))
    except StopIteration:
        return Catalogue(by_sig, attempts, True, max_nodes)
    return Catalogue(by_sig, attempts, False, max_nodes)


def synthesize(examples: Examples, max_nodes: int = 9, budget: int = 200000) -> dict:
    if not examples or any(type(x) is not int or type(y) is not int for x, y in examples):
        raise ValueError('integer input-output examples required')
    points = {}
    for x, y in examples:
        if x in points and points[x] != y:
            return {'status': 'inconsistent', 'candidate': None, 'attempts': 0}
        points[x] = y
    xs = tuple(points)
    ys = tuple(points[x] for x in xs)
    cat = catalogue(xs, max_nodes, budget)
    chosen: Optional[Candidate] = cat.by_signature.get(ys)
    return {'status': 'fit' if chosen else 'budget_or_grammar_exhausted',
            'candidate': chosen, 'attempts': chosen.attempt if chosen else cat.attempts,
            'shared_catalogue_attempts': cat.attempts,
            'shared_catalogue_signatures': len(cat.by_signature),
            'budget_hit': cat.budget_hit}
