"""标准库参考实现；不是进程隔离、开放语法创造或通用学习器。"""
from dataclasses import asdict, dataclass
from collections import deque
from itertools import combinations
from math import comb
import json
from typing import Callable, Dict, Iterable, List, Optional, Tuple


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def bits(n: int) -> int:
    return bin(n).count("1")


def canonical(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


@dataclass(frozen=True)
class Record:
    seq: int
    kind: str
    source: str
    body: str
    refs: Tuple[int, ...]
    deps: Tuple[int, ...]


class Ledger:
    """refs 是历史引用，deps 是证明依赖。撤销也作为新事件保存。"""
    def __init__(self) -> None:
        self.records: List[Record] = []
        self.children: Dict[int, set] = {}
        self.invalid: set = set()
        self.revoked: set = set()
        self.edges_visited = 0

    def add(self, kind: str, source: str, body: dict,
            refs: Tuple[int, ...] = (), deps: Tuple[int, ...] = ()) -> int:
        require(isinstance(source, str) and bool(source.strip()), "source required")
        require(isinstance(kind, str) and bool(kind), "kind required")
        for links in (refs, deps):
            require(isinstance(links, tuple), "immutable links required")
            require(all(type(v) is int and 0 <= v < len(self.records) for v in links),
                    "links must point to existing history")
            require(len(set(links)) == len(links), "duplicate links")
        require(not any(v in self.invalid for v in deps), "invalid proof dependency")
        seq = len(self.records)
        text = canonical(body).decode("utf-8")
        self.records.append(Record(seq, kind, source, text, refs, deps))
        for parent in deps:
            self.children.setdefault(parent, set()).add(seq)
        return seq

    def revoke(self, root: int, reason: str) -> Tuple[int, ...]:
        require(type(root) is int and 0 <= root < len(self.records), "unknown root")
        self.revoked.add(root)
        queue, changed = deque([root]), set()
        while queue:
            current = queue.popleft()
            if current in self.invalid:
                continue
            self.invalid.add(current)
            changed.add(current)
            children = self.children.get(current, ())
            self.edges_visited += len(children)
            queue.extend(children)
        self.add("revocation", "Queen/auditor", {"reason": reason, "root": root,
                 "invalidated": sorted(changed)}, refs=(root,))
        return tuple(sorted(changed))

    def recompute(self) -> set:
        """同信息全日志重算对照。"""
        invalid = set(self.revoked)
        for rec in self.records:
            if any(parent in invalid for parent in rec.deps):
                invalid.add(rec.seq)
        return invalid

    def export(self) -> list:
        return [asdict(rec) for rec in self.records]


def monomials(d: int, degree: int) -> Tuple[int, ...]:
    require(type(d) is int and 1 <= d <= 8, "1 <= dimension <= 8")
    require(type(degree) is int and 0 <= degree <= d, "invalid degree")
    return tuple(sorted((m for m in range(1 << d) if bits(m) <= degree),
                        key=lambda m: (bits(m), m)))


def features(x: int, terms: Tuple[int, ...]) -> int:
    return sum(1 << j for j, mask in enumerate(terms) if x & mask == mask)


def solve(rows: Iterable[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    """GF(2) 线性方程：自由变量设零，返回一解与秩；矛盾返回 None。"""
    basis: Dict[int, Tuple[int, int]] = {}
    for row, rhs in rows:
        require(type(row) is int and row >= 0 and type(rhs) is int and rhs in (0, 1),
                "invalid binary equation")
        while row:
            pivot = row.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (row, rhs)
                break
            other, value = basis[pivot]
            row, rhs = row ^ other, rhs ^ value
        if row == 0 and rhs:
            return None
    solution = 0
    for pivot in sorted(basis):
        row, rhs = basis[pivot]
        if (bits(row & solution) & 1) != rhs:
            solution |= 1 << pivot
    return solution, len(basis)


class PolynomialReader:
    """只接收观测；单项式语法预设，反例可迫使扩大次数。"""
    def __init__(self, d: int, maximum: Optional[int] = None) -> None:
        self.d = d
        self.maximum = d if maximum is None else maximum
        require(1 <= self.maximum <= d, "invalid maximum")
        self.degree, self.coefficients, self.rank = 1, 0, 0
        self.evidence: Dict[int, int] = {}
        self.expansions: List[Tuple[int, int, int]] = []
        self.ledger = Ledger()
        self.assumption = self.ledger.add("assumption", "Queen/model-v1", {"degree": 1})
        self.last_claim: Optional[int] = None
        self.failed = False
        self.refits = 0

    def predict(self, x: int) -> int:
        require(type(x) is int and 0 <= x < (1 << self.d), "input outside scope")
        require(not self.failed, "model inconsistent")
        return bits(features(x, monomials(self.d, self.degree)) & self.coefficients) & 1

    def observe(self, x: int, value: int) -> None:
        require(type(value) is int and value in (0, 1), "invalid observation")
        prediction = self.predict(x)
        if self.last_claim is not None:
            # 真正重读保存的旧判断器，而不是只给日志添加一条装饰性引用。
            prior = json.loads(self.ledger.records[self.last_claim].body)
            archived_prediction = bits(features(x, monomials(self.d, prior["degree"]))
                                       & prior["coefficients"]) & 1
            require(archived_prediction == prediction, "live and archived reader disagree")
            prediction = archived_prediction
        if x in self.evidence:
            require(self.evidence[x] == value, "stationarity or noise assumption failed")
            return
        obs = self.ledger.add("observation", "Worker/paired-sensor", {"x": x, "residual": value})
        refs = (obs,) if self.last_claim is None else (obs, self.last_claim)
        review = self.ledger.add("review", "Queen/auditor",
            {"prediction": prediction, "observed": value, "disagrees": prediction != value},
            refs=refs, deps=(obs,))
        self.evidence[x] = value
        while True:
            terms = monomials(self.d, self.degree)
            fitted = solve((features(point, terms), answer) for point, answer in self.evidence.items())
            self.refits += 1
            if fitted is not None:
                self.coefficients, self.rank = fitted
                break
            self.ledger.revoke(self.assumption, "no model at this degree fits the evidence")
            if self.degree == self.maximum:
                self.failed = True
                return
            old = self.degree
            self.degree += 1
            self.expansions.append((old, self.degree, x))
            self.assumption = self.ledger.add("assumption", "Queen/model-v" + str(self.degree),
                {"degree": self.degree, "trigger": x}, refs=(review,))
        dependencies = tuple(rec.seq for rec in self.ledger.records if rec.kind == "observation")
        self.last_claim = self.ledger.add("conditional_model", "Queen/model-v" + str(self.degree),
            {"degree": self.degree, "coefficients": self.coefficients, "rank": self.rank,
             "scope": "conditional_on_declared_grammar_not_global"},
            refs=(review,), deps=(self.assumption,) + dependencies)
        require(self.ledger.recompute() == self.ledger.invalid, "ledger mismatch")

    def table(self) -> int:
        return sum(self.predict(x) << x for x in range(1 << self.d))

    def certify_full_universe(self) -> bool:
        return not self.failed and len(self.evidence) == 1 << self.d


class World:
    """模拟器私有真值不传入学习器；公共接口不是恶意代码安全隔离。"""
    def __init__(self, d: int, residual: int, environment: int = 0) -> None:
        self.d, self._residual, self._environment = d, residual, environment
        self.calls = 0
        self.correction: Callable[[int], int] = lambda x: 0
        require(0 <= residual < (1 << (1 << d)), "truth table outside domain")

    def observe(self, x: int, b: int = 0, bypass: bool = False) -> int:
        require(0 <= x < (1 << self.d) and b in (0, 1), "invalid world input")
        self.calls += 1
        internal = 0 if bypass else ((self._residual >> x) & 1)
        return b ^ internal ^ ((self._environment >> x) & 1)

    def paired(self, x: int) -> int:
        return self.observe(x) ^ self.observe(x, bypass=True)

    def execute(self, x: int, b: int) -> int:
        # 中性受控环境中的独立实际执行，不进入拟合过程。
        return b ^ ((self._residual >> x) & 1) ^ self.correction(x)


def acceptable(candidates: Iterable[int], modifications: Dict[int, set]) -> set:
    worlds = tuple(candidates)
    if not worlds:
        return set()
    return set.intersection(*(set(modifications[h]) for h in worlds))


def majority_error(n: int, p: float) -> float:
    require(type(n) is int and n > 0 and n % 2 == 1, "positive odd repetition count")
    require(0 <= p < 0.5, "noise rate must be < 1/2")
    return sum(comb(n, k) * p ** k * (1 - p) ** (n - k)
               for k in range(n // 2 + 1, n + 1))


def repetitions(domain: int, p: float, delta: float) -> int:
    require(domain > 0 and 0 < delta < 1, "invalid probability budget")
    for n in range(1, 1000, 2):
        if domain * majority_error(n, p) <= delta:
            return n
    raise ValueError("repetition budget exceeded")
