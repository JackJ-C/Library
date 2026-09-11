"""仅标准库的 M0 参考契约。约束公共接口，不提供恶意进程隔离。"""
from collections import deque
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from typing import Any, Dict, Optional, Tuple


class ContractError(ValueError):
    """请求违反 M0 数据或可见性契约。"""


def natural(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ContractError(name + " must be an integer >= " + str(minimum))


def text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("nonempty text required")


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ContractError("finite JSON required") from exc


@dataclass(frozen=True)
class Actor:
    instance: str
    version: str

    def __post_init__(self) -> None:
        text(self.instance)
        text(self.version)


@dataclass(frozen=True)
class Slice:
    key: str
    source: Actor
    event: int
    available: int
    kind: str
    body: str
    refs: Tuple[str, ...]

    def payload(self) -> Dict[str, Any]:
        # 每次解码生成副本，调用者不能借嵌套字典修改已保存记录。
        return json.loads(self.body)

    def serial(self) -> str:
        return canonical(asdict(self))


@dataclass(frozen=True)
class Reading:
    record: Slice
    reader: Actor
    horizon: int


@dataclass(frozen=True)
class Traversal:
    keys: Tuple[str, ...]
    truncated: bool
    bytes_read: int


class Library:
    def __init__(self) -> None:
        self._records: Dict[str, Slice] = {}
        self._clock = -1

    def append(self, key: str, source: Actor, event: int, available: int,
               payload: Dict[str, Any], kind: str = "experience",
               refs: Tuple[str, ...] = ()) -> Slice:
        text(key)
        natural(event, "event")
        natural(available, "available")
        if not isinstance(source, Actor) or not isinstance(payload, dict):
            raise ContractError("Actor and dictionary payload required")
        if key in self._records or event > available or available <= self._clock:
            raise ContractError("duplicate key or invalid logical time")
        if kind not in ("experience", "review"):
            raise ContractError("unknown record kind")
        if not isinstance(refs, tuple) or any(not isinstance(k, str) for k in refs):
            raise ContractError("immutable string references required")
        if len(set(refs)) != len(refs):
            raise ContractError("duplicate reference")
        if any(k not in self._records for k in refs):
            raise ContractError("references must already exist")
        if kind == "review" and not refs:
            raise ContractError("a review must reference its evidence")
        record = Slice(key, source, event, available, kind, canonical(payload), refs)
        self._records[key] = record
        self._clock = available
        return record

    def read(self, key: str, horizon: int, reader: Actor) -> Reading:
        natural(horizon, "horizon")
        if not isinstance(reader, Actor):
            raise ContractError("Actor reader required")
        if key not in self._records:
            raise ContractError("unknown slice")
        record = self._records[key]
        if record.available > horizon:
            raise ContractError("evidence not yet available at this horizon")
        return Reading(record, reader, horizon)

    def traverse(self, key: str, horizon: int, reader: Actor, *,
                 max_nodes: int = 32, max_depth: int = 4,
                 max_bytes: int = 16384) -> Traversal:
        natural(max_nodes, "max_nodes", 1)
        natural(max_depth, "max_depth")
        natural(max_bytes, "max_bytes", 1)
        self.read(key, horizon, reader)
        queue = deque([(key, 0)])
        seen, blocked, output = set(), set(), []
        used = 0
        while queue:
            current, depth = queue.popleft()
            if current in seen:
                continue
            record = self.read(current, horizon, reader).record
            size = len(record.serial().encode("utf-8"))
            if len(output) >= max_nodes or used + size > max_bytes:
                blocked.add(current)
                continue
            seen.add(current)
            output.append(current)
            used += size
            if depth < max_depth:
                queue.extend((ref, depth + 1) for ref in record.refs)
            else:
                blocked.update(record.refs)
        return Traversal(tuple(output), bool(blocked - seen), used)


def evidence_digest(records: Tuple[Slice, ...]) -> str:
    # 顺序本身可能是信息，不能排序后假装两个读取过程完全相同。
    return sha256(canonical([r.serial() for r in records]).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Judgment:
    reader: Actor
    question: str
    target: str
    evidence: str
    horizon: int
    value: Optional[float]
    random_key: str = "fixed"

    def __post_init__(self) -> None:
        if not isinstance(self.reader, Actor):
            raise ContractError("Actor reader required")
        for field in (self.question, self.target, self.evidence, self.random_key):
            text(field)
        natural(self.horizon, "horizon")
        if self.value is not None and (type(self.value) not in (int, float)
                                       or not math.isfinite(self.value)):
            raise ContractError("finite numerical judgment or None required")


def gap(old: Judgment, new: Judgment) -> Dict[str, Any]:
    # 这里只检查声明的条件；不能认证调用者没有隐藏输入或伪造摘要。
    conditions = ("question", "target", "evidence", "horizon", "random_key")
    if any(getattr(old, k) != getattr(new, k) for k in conditions):
        return {"status": "not_comparable", "gap": None}
    if old.value is None or new.value is None:
        return {"status": "unknown", "gap": None}
    return {"status": "comparable", "gap": abs(old.value - new.value)}


def square(j00: int, j01: int, j10: int, j11: int) -> Dict[str, int]:
    """有限整数判断的四格代数；不是因果估计器或改善判定器。"""
    if any(type(v) is not int for v in (j00, j01, j10, j11)):
        raise ContractError("four integer judgments required")
    return {"reader": j10 - j00, "evidence": j01 - j00,
            "interaction": j11 - j10 - j01 + j00, "total": j11 - j00}
