"""公开模型族、受控世界、证据视图及两步补证据规划；仅标准库。"""
from dataclasses import dataclass
from functools import lru_cache
import json


def parity(n):
    return n.bit_count() % 2


def params(h):
    return tuple((h >> (2 * j)) & 3 for j in range(4))


def repair(h):
    w, c, q, _ = params(h)
    return w ^ c ^ q


@dataclass(frozen=True)
class Probe:
    context: int
    route: int

    def __post_init__(self):
        if type(self.context) is not int or not 0 <= self.context < 4:
            raise ValueError("context must be a two-bit integer")
        if type(self.route) is not int or not 0 <= self.route < 8:
            raise ValueError("route must be a three-bit integer")


QUERIES = tuple(Probe(x, route) for x in (1, 2) for route in range(8))


class World:
    """只有实验驱动器拥有实例；Agent 仅得到 step 返回的终端读数。"""
    def __init__(self, hidden, nonlinear=False):
        if type(hidden) is not int or not 0 <= hidden < 256:
            raise ValueError("hidden world outside finite family")
        self._parts = params(hidden)
        self._nonlinear = nonlinear

    def step(self, probe, correction=0, payload=0, neutral=False):
        if type(correction) is not int or not 0 <= correction < 4:
            raise ValueError("invalid bounded correction")
        if type(payload) is not int or payload not in (0, 1):
            raise ValueError("invalid payload")
        out = payload
        # 与推断器的压平线性表达分开，逐级执行传播。
        for j in range(3):
            if (probe.route >> j) & 1:
                lo = (self._parts[j] & 1) * (probe.context & 1)
                hi = ((self._parts[j] >> 1) & 1) * ((probe.context >> 1) & 1)
                out ^= (lo + hi) % 2
        if self._nonlinear and probe.route == 7 and probe.context == 3:
            out ^= 1
        out ^= parity(correction & probe.context)
        if not neutral:
            out ^= parity(self._parts[3] & probe.context)
        return out


class Trace:
    """序列化快照；来源/视野契约，不是恶意代码安全沙箱。"""
    def __init__(self):
        self._rows = []

    def append(self, kind, source, scope, body, refs=()):
        seq = len(self._rows)
        if any(type(i) is not int or i < 0 or i >= seq for i in refs):
            raise ValueError("references must point to existing records")
        row = dict(seq=seq, available=seq, kind=kind, source=source,
                   scope=scope, body=body, refs=list(refs))
        self._rows.append(json.dumps(row, sort_keys=True, allow_nan=False))
        return seq

    def read(self, seq, horizon):
        if type(seq) is not int or not 0 <= seq < len(self._rows):
            raise ValueError("unknown record")
        row = json.loads(self._rows[seq])
        if row["available"] > horizon:
            raise ValueError("future evidence")
        return row

    def evidence(self, scope, horizon):
        return [r for r in self.export() if r["available"] <= horizon
                and r["scope"] == scope and r["kind"] == "observation"]

    def export(self):
        return [json.loads(r) for r in self._rows]


class Model:
    """不知道真实 h；枚举公开的 256 种机制，用 bitset 保存兼容集。"""
    def __init__(self):
        self.all = (1 << 256) - 1
        self.ones = []
        for p in QUERIES:
            row = p.context << 6
            for j in range(3):
                if (p.route >> j) & 1:
                    row |= p.context << (2 * j)
            self.ones.append(sum(1 << h for h in range(256) if parity(h & row)))
        self.repairs = tuple(sum(1 << h for h in range(256) if repair(h) == r)
                             for r in range(4))

    def update(self, state, query, observation):
        if query not in range(len(QUERIES)) or observation not in (0, 1):
            raise ValueError("invalid measurement")
        mask = self.ones[query] if observation else self.all ^ self.ones[query]
        return state & mask

    def parts(self, state, query):
        return tuple(s for s in (state & self.ones[query],
                                 state & (self.all ^ self.ones[query])) if s)

    @lru_cache(maxsize=None)
    def options(self, state):
        return tuple(r for r, mask in enumerate(self.repairs) if state & mask)

    @lru_cache(maxsize=None)
    def choose(self, state, identity=False):
        if not state:
            return None
        count = int.bit_count if identity else lambda s: len(self.options(s))
        if count(state) == 1:
            return None
        scored = []
        for i in range(len(QUERIES)):
            branches = self.parts(state, i)
            if len(branches) < 2:
                continue
            if identity:
                score = (max(map(count, branches)), i)
            else:
                # 两步最坏剩余修复数；不直接以识别全部 h 为目标。
                future = [min(max(count(t) for t in self.parts(s, j))
                              for j in range(len(QUERIES))) for s in branches]
                score = (max(future), max(map(count, branches)), i)
            scored.append((score, i))
        return min(scored)[1] if scored else None

    def replay(self, rows, initial=None):
        state = self.all if initial is None else initial
        for row in rows:
            b = row["body"]
            raw = b["output"] ^ b["payload"] ^ parity(b["correction"] & b["context"])
            state = self.update(state, b["query"], raw)
        return state

    def transition(self, state, changed):
        """已声明哪些槽位可能变化；未知新值全部保留，而非继承旧答案。"""
        if any(j not in range(4) for j in changed):
            raise ValueError("unknown component")
        keep = 255
        for j in changed:
            keep &= ~(3 << (2 * j))
        stable = {h & keep for h in range(256) if (state >> h) & 1}
        return sum(1 << h for h in range(256) if (h & keep) in stable)


def episode(model, sensor, policy="library", initial=None, order=None,
            scope="system-A/v0", correction=0):
    state = model.all if initial is None else initial
    trace = Trace()
    queries, latest, cursor = [], None, 0
    for _ in range(len(QUERIES)):
        identity = policy == "identity"
        if not state or (state.bit_count() == 1 if identity else len(model.options(state)) == 1):
            break
        if policy in ("random", "passive"):
            if order is None or cursor >= len(order):
                break
            qid = order[cursor]
            cursor += 1
        else:
            qid = model.choose(state, identity)
        if qid is None:
            break
        p = QUERIES[qid]
        action = trace.append("action", "worker/v0", scope,
                              dict(query=qid, context=p.context, route=p.route,
                                   payload=0, correction=correction))
        y = sensor(p, correction=correction)
        observation = trace.append("observation", "endpoint-sensor/v0", scope,
                                   dict(query=qid, context=p.context, route=p.route,
                                        output=y, payload=0, correction=correction), (action,))
        before = model.options(state)
        if policy == "flat":
            state = model.replay(trace.evidence(scope, observation), initial)
        else:
            state = model.update(state, qid, y ^ parity(correction & p.context))
        after = model.options(state)
        refs = (observation,) if latest is None else (latest, observation)
        latest = trace.append("review", "queen/diagnoser-v1", scope,
                              dict(hypotheses=state.bit_count(), before=list(before),
                                   alternatives=list(after),
                                   status="inconsistent" if not state else
                                   "repair_identified" if len(after) == 1 else "need_evidence",
                                   falsifier="a new controlled observation excludes all candidates"), refs)
        queries.append(qid)
    options = model.options(state)
    selected = options[0] if len(options) == 1 else None
    trace.append("proposal", "queen/diagnoser-v1", scope,
                 dict(correction=selected, hypotheses=state.bit_count()),
                 () if latest is None else (latest,))
    return dict(state=state, repair=selected, queries=queries, trace=trace.export())


def validate(sensor, old, candidate):
    """先冻结候选，再独立运行组合情境、保持项和原情境回归，不反馈给规划器。"""
    if candidate is None:
        return dict(accepted=False, status="abstain", rows=[])
    rows = []
    for x in (3, 0, 1, 2):
        for payload in (0, 1):
            p = Probe(x, 7)
            a = sensor(p, correction=old, payload=payload, neutral=True)
            b = sensor(p, correction=candidate, payload=payload, neutral=True)
            rows.append(dict(context=x, payload=payload, split="heldout" if x in (3, 0) else "regression",
                             old_ok=a == payload, new_ok=b == payload))
    ok = all(r["new_ok"] for r in rows)
    return dict(accepted=ok, status="adopt" if ok and candidate != old else
                "no_change" if ok else "reject", rows=rows)


@dataclass(frozen=True)
class Genome:
    correction: int = 0
    version: int = 0

    def __post_init__(self):
        if type(self.correction) is not int or not 0 <= self.correction < 4:
            raise ValueError("genome outside bounded repair space")
        if type(self.version) is not int or self.version < 0:
            raise ValueError("invalid genome version")


class Controller:
    """固定诊断器 + 可持久改变的 Queen 输出校正；不是任意源码自修改。"""
    def __init__(self, model, sensor):
        self.model, self.sensor = model, sensor
        self.genome = Genome()
        self.lineage = [self.genome]

    def act(self, probe, payload=0, neutral=False):
        return self.sensor(probe, correction=self.genome.correction,
                           payload=payload, neutral=neutral)

    def cycle(self):
        old = self.genome
        run = episode(self.model, self.sensor, correction=old.correction,
                      scope="system-A/" + str(old.version))
        gate = validate(self.sensor, old.correction, run["repair"])
        if gate["accepted"] and run["repair"] != old.correction:
            self.genome = Genome(run["repair"], old.version + 1)
            self.lineage.append(self.genome)
        run["deployment"] = dict(old_correction=old.correction, new_correction=self.genome.correction,
                                 old_version=old.version, new_version=self.genome.version,
                                 status=gate["status"], parent_version=old.version)
        return run, gate
