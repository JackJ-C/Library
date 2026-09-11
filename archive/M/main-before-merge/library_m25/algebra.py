"""独立稀疏多项式正规形检查。不调用枚举器，不用采样等式代替恒等式。"""
from dataclasses import dataclass


@dataclass
class Poly:
    terms: dict

    @staticmethod
    def constant(n): return Poly({(): n} if n else {})
    @staticmethod
    def variable(name): return Poly({(name,): 1})

    def __add__(self, other):
        result = dict(self.terms)
        for key, value in other.terms.items():
            result[key] = result.get(key, 0) + value
            if result[key] == 0: del result[key]
        return Poly(result)

    def __neg__(self): return Poly({k: -v for k, v in self.terms.items()})
    def __sub__(self, other): return self + (-other)

    def __mul__(self, other):
        result = {}
        for a, av in self.terms.items():
            for b, bv in other.terms.items():
                key = tuple(sorted(a + b))
                result[key] = result.get(key, 0) + av * bv
        return Poly({k: v for k, v in result.items() if v})

    def zero(self): return not self.terms
    def export(self): return [[list(k), v] for k, v in sorted(self.terms.items())]


def interpret(expr, bindings):
    op = expr[0]
    if op == 'v': return bindings[expr[1]]
    if op == 'c': return Poly.constant(expr[1])
    a, b = interpret(expr[1], bindings), interpret(expr[2], bindings)
    if op == '+': return a + b
    if op == '-': return a - b
    if op == '*': return a * b
    raise ValueError('polynomial proof requires polynomial expression')


def builder_value(expr, x, fx, f0, f1, previous=None):
    values = dict(x=x, fx=fx, f0=f0, f1=f1)
    if previous is not None:
        values['tx'] = builder_value(previous, x, fx, f0, f1)
        values['t0'] = builder_value(previous, Poly.constant(0), f0, f0, f1)
        values['t1'] = builder_value(previous, Poly.constant(1), f1, f0, f1)
    return interpret(expr, values)


def prove_builder(expr, level, previous=None):
    X, F, F0, F1, A, B = [Poly.variable(n) for n in ('X', 'F', 'F0', 'F1', 'A', 'B')]
    z, one = Poly.constant(0), Poly.constant(1)
    original = builder_value(expr, X, F, F0, F1, previous)
    if level == 0:
        changed = builder_value(expr, X, F+B, F0+B, F1+B, previous)
        preserve = builder_value(expr, X, F, z, F1, previous) - F
    else:
        changed = builder_value(expr, X, F+A*X+B, F0+B, F1+A+B, previous)
        preserve = builder_value(expr, X, F, z, z, previous) - F
    identities = {
        'nuisance_invariance': changed-original,
        'anchor_zero': builder_value(expr, z, F0, F0, F1, previous),
        'preserve_normalized_function': preserve,
    }
    if level == 1:
        identities['anchor_one'] = builder_value(expr, one, F1, F0, F1, previous)
    return {'passed': all(p.zero() for p in identities.values()),
            'normal_form': original.export(),
            'obligations': {name: p.export() for name, p in identities.items()},
            'scope': 'integer functions under exact declared call/arithmetic semantics'}


def prove_search(expr):
    # 只核验实际AST；这里不预装正确搜索公式。
    A, B, P, Q = [Poly.variable(n) for n in ('A', 'B', 'P', 'Q')]
    env = dict(p0=P, p1=Q, r0=A*P+B, r1=A*Q+B)
    if expr[0] == '/':
        num, den = interpret(expr[1], env), interpret(expr[2], env)
    else:
        num, den = interpret(expr, env), Poly.constant(1)
    residual_numerator = A*num + B*den
    delta = P-Q
    expected_forms = (A*delta, -(A*delta))
    domain_proved = any((den-v).zero() for v in expected_forms)
    return {'passed': residual_numerator.zero() and domain_proved,
            'residual_numerator': residual_numerator.export(),
            'denominator': den.export(),
            'denominator_is_signed_A_times_P_minus_Q': domain_proved,
            'assumptions': ['nonzero affine slope A', 'P != Q', 'exact rational arithmetic'],
            'scope': 'root proposal law only; not arbitrary nonlinear search'}
