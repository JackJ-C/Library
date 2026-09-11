"""M1–M7：有限确定性实验；标准库；诊断器不读取模拟器真参数。

公开接口检查不等于对恶意同进程 Python 的安全隔离。
"""
from dataclasses import asdict, dataclass
from itertools import product
import json
import random

PARAMS = tuple(product(range(4), repeat=4))
QUERIES = tuple((m, x) for m in range(8) for x in (1, 2))
ALL = (1 << 256) - 1
PASSIVE = (14, 15)
VALIDATION = ((0, 1), (1, 1), (2, 1))
CHALLENGE = ((3, 0), (3, 1), (0, 0))
CASES = tuple(product(range(4), range(2)))


def encode(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def repair(h):
    return h[0] ^ h[1] ^ h[2]


def prediction(h, q):
    m, x = QUERIES[q]
    coefficient = h[3]
    for i in range(3):
        if m & (1 << i):
            coefficient ^= h[i]
    return (coefficient & x).bit_count() % 2


# 所有策略共享 256*16=4096 次公开模型预测，不是环境交互。
ONES = tuple(sum(1 << i for i, h in enumerate(PARAMS) if prediction(h, q)) for q in range(16))
CLASSES = tuple(sum(1 << i for i, h in enumerate(PARAMS) if repair(h) == u) for u in range(4))


def ids(H):
    return [i for i in range(256) if H & (1 << i)]


def choices(H):
    return [u for u, group in enumerate(CLASSES) if H & group]


def filter_H(H, q, y):
    require(type(q) is int and 0 <= q < 16 and type(y) is int and y in (0, 1), 'invalid observation')
    return H & (ONES[q] if y else ALL ^ ONES[q])


def resolved(H, purpose):
    require(purpose in ('repair', 'identify'), 'invalid purpose')
    return bool(H) and (H.bit_count() == 1 if purpose == 'identify' else len(choices(H)) == 1)


def cross_pairs(H, purpose):
    n = H.bit_count()
    if purpose == 'identify':
        return n * (n - 1) // 2
    return (n*n - sum((H & group).bit_count() ** 2 for group in CLASSES)) // 2


def next_query(H, remaining, purpose, cost):
    n = H.bit_count()
    before = cross_pairs(H, purpose)
    best, score = None, -1
    for q in remaining:
        H1, H0 = H & ONES[q], H & (ALL ^ ONES[q])
        gain = n*before - H1.bit_count()*cross_pairs(H1, purpose) - H0.bit_count()*cross_pairs(H0, purpose)
        cost['queries_scored'] += 1
        cost['class_counts'] += 8 if purpose == 'repair' else 0
        if gain > score:
            best, score = q, gain
    return best if score > 0 else None


class World:
    """逐阶段模拟，与公开预测器的系数合并实现相互独立。"""
    def __init__(self, theta, nonlinear=False, payload_fault=False):
        require(tuple(theta) in PARAMS, 'invalid world')
        self._theta = tuple(theta)
        self.nonlinear = nonlinear
        self.payload_fault = payload_fault
        self.correction = 0

    def execute(self, x, b, mask=7, neutral=False):
        require(type(x) is int and 0 <= x < 4 and type(b) is int and b in (0, 1), 'invalid input')
        require(type(mask) is int and 0 <= mask < 8, 'invalid mask')
        y = b
        for stage, coeff in enumerate(self._theta):
            enabled = (not neutral) if stage == 3 else bool(mask & (1 << stage))
            if enabled:
                for bit in range(2):
                    if (coeff >> bit) & 1 and (x >> bit) & 1:
                        y = 1 - y
                if stage == 0 and ((self.nonlinear and x == 3) or (self.payload_fault and b == 1)):
                    y = 1 - y
        for bit in range(2):
            if (self.correction >> bit) & 1 and (x >> bit) & 1:
                y = 1 - y
        return y

    def observe(self, q):
        require(type(q) is int and 0 <= q < 16, 'invalid query')
        mask, x = QUERIES[q]
        return self.execute(x, 0, mask)

    def apply(self, u):
        require(type(u) is int and 0 <= u < 4, 'invalid bounded correction')
        self.correction = u


@dataclass(frozen=True)
class Record:
    key: int
    source: str
    target_version: str
    event: int
    available: int
    kind: str
    body: str
    refs: tuple


class Ledger:
    """dict 关系库或普通顺序日志；记录包含完全相同的信息。"""
    def __init__(self, backend='library'):
        require(backend in ('library', 'plain'), 'invalid backend')
        self.backend = backend
        self.records = []
        self.index = {}

    def append(self, source, version, kind, body, refs=()):
        key = len(self.records)
        require(source in ('worker', 'rig', 'queen'), 'invalid source')
        require(bool(version) and kind in ('action', 'feedback', 'review'), 'invalid metadata')
        require(all(type(r) is int and 0 <= r < key for r in refs), 'future reference')
        r = Record(key, source, version, key, key, kind, encode(body), tuple(refs))
        self.records.append(r)
        self.index[key] = r
        return key

    def read(self, key, horizon):
        if self.backend == 'library':
            r = self.index.get(key)
        else:
            r = next((r for r in self.records if r.key == key), None)
        require(r is not None and r.available <= horizon, 'unknown or future evidence')
        return r


def feedback(r, version):
    require(r.source == 'rig' and r.kind == 'feedback' and r.target_version == version, 'wrong provenance/version')
    data = json.loads(r.body)
    q, y = data['q'], data['y']
    filter_H(ALL, q, y)
    return q, y


def diagnose(observe, purpose='repair', policy='active', backend='library', initial=ALL,
             prefix=PASSIVE, seed=0, trace=False, version='v0'):
    """只经 observe 取数据。候选模型族已知，不是开放式未知机制发现。"""
    require(policy in ('active', 'passive', 'random'), 'unknown policy')
    require(type(initial) is int and 0 < initial <= ALL, 'invalid initial hypotheses')
    ledger, history, feedback_keys, last_review = Ledger(backend), [], [], None
    cost = dict(interactions=0, filters=0, queries_scored=0, class_counts=0, reads=0, bytes_read=0, writes=0)
    rng = random.Random(seed)
    H, unused = initial, list(range(16))
    while len(history) < 16:
        if len(history) < len(prefix):
            q = prefix[len(history)]
        elif resolved(H, purpose) or not H:
            break
        elif policy == 'passive':
            break
        elif policy == 'random':
            q = rng.choice(unused)
        else:
            q = next_query(H, unused, purpose, cost)
            if q is None:
                break
        require(q in unused, 'query repeated')
        unused.remove(q)
        y = observe(q)
        filter_H(ALL, q, y)
        history.append((q, y))
        cost['interactions'] += 1
        old_choices = choices(H)
        if trace:
            action = ledger.append('worker', version, 'action', {'q': q, 'mask': QUERIES[q][0], 'x': QUERIES[q][1], 'b': 0})
            key = ledger.append('rig', version, 'feedback', {'q': q, 'y': y}, (action,))
            feedback_keys.append(key)
            data = []
            for key in feedback_keys:
                r = ledger.read(key, len(ledger.records)-1)
                cost['reads'] += 1
                cost['bytes_read'] += len(encode(asdict(r)).encode())
                data.append(feedback(r, version))
            if last_review is not None:
                old = ledger.read(last_review, len(ledger.records)-1)
                old_choices = json.loads(old.body)['repair_options']
                cost['reads'] += 1
                cost['bytes_read'] += len(encode(asdict(old)).encode())
        else:
            data = history
        H = initial
        for q0, y0 in data:
            H = filter_H(H, q0, y0)
            cost['filters'] += 1
        if trace:
            refs = tuple(feedback_keys) + (() if last_review is None else (last_review,))
            last_review = ledger.append('queen', version, 'review', {
                'candidates': H.bit_count(), 'repair_options': choices(H),
                'prior_options': old_choices, 'revised': old_choices != choices(H),
                'status': 'inconsistent' if not H else ('sufficient' if resolved(H, purpose) else 'probe_needed'),
                'refutation': 'a future output incompatible with every retained hypothesis',
                'scope': 'known deterministic family; target internal net transfer'
            }, refs)
    cost['writes'] = len(ledger.records)
    return {'H': H, 'choices': choices(H), 'status': 'inconsistent' if not H else ('sufficient' if resolved(H, purpose) else 'unresolved'),
            'history': history, 'cost': cost, 'records': [asdict(r) for r in ledger.records]}


def lift(old_H, changed):
    require(bool(old_H) and set(changed) <= set(range(4)), 'invalid transition scope')
    old = [PARAMS[i] for i in ids(old_H)]
    return sum(1 << j for j, h in enumerate(PARAMS)
               if any(all(h[k] == o[k] for k in range(4) if k not in changed) for o in old))


def adopt(world, u):
    """先真实执行验证，再采用或回退；挑战仅评价，不用于重选。"""
    old = world.correction
    before = [world.execute(x, b, neutral=True) == b for x, b in VALIDATION]
    world.apply(u)
    after = [world.execute(x, b, neutral=True) == b for x, b in VALIDATION]
    accepted = all(after) and all(not a or z for a, z in zip(before, after))
    if not accepted:
        world.apply(old)
    challenge = [world.execute(x, b, neutral=True) == b for x, b in CHALLENGE]
    return {'accepted': accepted, 'before': before, 'after': after, 'challenge': challenge,
            'regressions': sum(a and not z for a, z in zip(before, after)), 'applied': world.correction}


def model_accepts(h, u):
    """M7：独立于模拟器的合同公式：内部正确且保持旧自然成功。"""
    r, e = repair(h), h[3]
    if u != r:
        return False
    return all(((r ^ e) & x).bit_count() % 2 != 0 or (e & x).bit_count() % 2 == 0 for x in range(4))


def common_safe(H):
    require(H > 0, 'empty evidence cannot certify')
    return [u for u in range(4) if all(model_accepts(PARAMS[i], u) for i in ids(H))]
