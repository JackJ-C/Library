"""四个同构审查单元的条件恢复；不把固定安装器隐藏成可自修对象。

六个真实调用槽均可失效；行为探针和票决安装器在单元外。
复制同伴函数是冗余恢复，不是合成新审查算法。同进程实现不抗恶意代码。
"""
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from functools import lru_cache
import inspect
import json
from typing import Callable, Tuple
from .synthesis import compile_expr, synthesize

SLOTS = ('decide', 'read', 'generate', 'validate', 'audit', 'schedule')


def digest(data) -> str:
    return sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=128)
def function_digest(fn: Callable) -> str:
    # 只用于绑定/票决身份，不拿摘要查询“正确函数表”。
    return sha256(inspect.getsource(fn).encode()).hexdigest()


def task(program, x): return program(x)
def read_epoch(rows, epoch): return tuple(r for r in rows if r[0] == epoch)
def generate(examples): return synthesize(examples)
def validate(program, examples): return all(program(x) == y for x, y in examples)
def audit(checks): return {slot: all(actual == expected for actual, expected in rows)
                          for slot, rows in checks.items()}
def schedule(items): return tuple(sorted(items))

def wrong_task(program, x): return 42
def wrong_read(rows, epoch): return tuple(rows)
def wrong_generate(examples): return {'status': 'fit', 'candidate': None}
def wrong_validate(program, examples): return True
def wrong_audit(checks): return {slot: True for slot in checks}
def wrong_schedule(items): return ()
def raises(*args, **kwargs): raise RuntimeError('injected execution failure')


class Cell:
    def __init__(self, name: str):
        self.name, self.version = name, 0
        self.functions = dict(zip(SLOTS, (task, read_epoch, generate, validate, audit, schedule)))
        self.program = compile_expr(('x',))
        self.calls = 0
        self.history = []

    def call(self, slot, *args):
        self.calls += 1
        return self.functions[slot](*args)

    def decide(self, x):
        return self.call('decide', self.program, x)

    def infer(self, examples, epoch):
        rows = tuple((epoch, x, y) for x, y in examples)
        self.history.extend(rows)
        selected = self.call('read', tuple(self.history), epoch)
        return self.call('generate', tuple((x, y) for _, x, y in selected))

    def deploy(self, program, examples):
        if self.call('validate', program, examples) is True:
            self.program = program
            return True
        return False

    def fault(self, mask: int, mode: str):
        # 此接口只有评估器调用；诊断器不读取 mask/mode，也不保存标签。
        wrong = dict(zip(SLOTS, (wrong_task, wrong_read, wrong_generate,
                                wrong_validate, wrong_audit, wrong_schedule)))
        if not 0 <= mask < 64 or mode not in ('silent', 'exception'):
            raise ValueError('invalid fault injection')
        for bit, slot in enumerate(SLOTS):
            if mask & (1 << bit):
                self.functions[slot] = wrong[slot] if mode == 'silent' else raises


def probe(cell: Cell) -> dict:
    """公开行为合同的隔离探针。不根据函数名称或故障编号判断。

    仅测试规定的输入，未声称等价于所有代码正确性证明。
    """
    checks = {}
    def check(slot, fn, expected):
        try:
            actual = fn()
        except Exception as exc:
            actual = {'raised': type(exc).__name__}
        checks.setdefault(slot, []).append((actual, expected))
    program = compile_expr(('add', ('x',), ('c', 1)))
    check('decide', lambda: cell.call('decide', program, 7), 8)
    check('decide', lambda: cell.call('decide', program, -4), -3)
    check('read', lambda: cell.call('read', ((0, 1, 2), (1, 1, 3)), 1), ((1, 1, 3),))
    def generated_values():
        answer = cell.call('generate', ((-1, 0), (0, 1), (2, 3)))
        candidate = answer.get('candidate')
        if answer.get('status') != 'fit' or candidate is None:
            return None
        p = compile_expr(candidate.expression)
        return tuple(p(x) for x in (-1, 0, 2))
    check('generate', generated_values, (0, 1, 3))
    check('validate', lambda: cell.call('validate', program, ((1, 99),)), False)
    check('validate', lambda: cell.call('validate', program, ((1, 2),)), True)
    check('audit', lambda: cell.call('audit', {'ok': [(1, 1)], 'bad': [(1, 0)]}),
          {'ok': True, 'bad': False})
    check('schedule', lambda: cell.call('schedule', (2, 0, 1)), (0, 1, 2))
    return checks


@dataclass(frozen=True)
class Context:
    subject: str
    version: int
    evidence: str
    candidate: str
    slot: str


@dataclass(frozen=True)
class Ballot:
    issuer: str
    context: Context
    approved: bool


def quorum(ballots: Tuple[Ballot, ...], context: Context, registry: tuple,
           desired: bool = True, threshold: int = 2) -> tuple:
    """固定协议条件：不自投、不重复计票、不跨版本/证据/候选复用。

    issuer 的认证靠调用方注册，字符串自身不是签名。这不是分布式共识实现。
    """
    matching = [b for b in ballots if b.issuer in registry and b.issuer != context.subject
                and b.context == context and type(b.approved) is bool]
    by_issuer = {}
    for b in matching:
        by_issuer.setdefault(b.issuer, set()).add(b.approved)
    # 同一上下文互相矛盾的票不能择其有利者计入。
    voters = tuple(sorted(i for i, opinions in by_issuer.items() if opinions == {desired}))
    return voters if len(voters) >= threshold else ()


def recover(cells: list) -> dict:
    """同一稳定快照内收票，批量绑定；不读取评估器的正确状态。

    probe 与 quorum/实际安装是剩余可信基础；六槽不是整个软件宇宙。
    """
    if len(cells) != 4 or len({c.name for c in cells}) != 4:
        raise ValueError('four registered instances required')
    registry = tuple(c.name for c in cells)
    versions = {c.name: c.version for c in cells}
    before = {c.name: dict(c.functions) for c in cells}
    reports = {c.name: probe(c) for c in cells}
    contexts = {(c.name, s): Context(c.name, c.version, digest(reports[c.name]),
                                    function_digest(c.functions[s]), s)
                for c in cells for s in SLOTS}
    ballots, inspections = [], []
    for voter in cells:
        for target in cells:
            if voter is target:
                continue
            try:
                verdicts = voter.call('audit', reports[target.name])
                if not isinstance(verdicts, dict):
                    raise ValueError('invalid audit result')
                for slot in SLOTS:
                    v = verdicts.get(slot)
                    if type(v) is bool:
                        ballots.append(Ballot(voter.name, contexts[target.name, slot], v))
                inspections.append([voter.name, target.name, verdicts])
            except Exception as exc:
                inspections.append([voter.name, target.name, {'raised': type(exc).__name__}])
    ballots = tuple(ballots)
    status, plans, unresolved = {}, {}, []
    for target in cells:
        for slot in SLOTS:
            ctx = contexts[target.name, slot]
            yes, no = quorum(ballots, ctx, registry), quorum(ballots, ctx, registry, False)
            status[target.name, slot] = True if yes else (False if no else None)
            if not yes and not no:
                unresolved.append([target.name, slot])
    for target in cells:
        patch = {}
        for slot in SLOTS:
            if status[target.name, slot] is False:
                donors = [d for d in cells if d is not target and status[d.name, slot] is True]
                if donors:
                    donor = min(donors, key=lambda d: d.name)
                    patch[slot] = donor
                else:
                    unresolved.append([target.name, slot])
        if patch:
            plans[target.name] = patch
    schedules = []
    for c in cells:
        try:
            order = c.call('schedule', tuple(plans))
            if isinstance(order, tuple): schedules.append(order)
        except Exception:
            pass
    counts = Counter(schedules)
    order = next((s for s, count in counts.items()
                  if count >= 3 and len(s) == len(plans) and set(s) == set(plans)), None)
    changes = []
    if order is not None:
        for name in order:
            target = next(c for c in cells if c.name == name)
            if target.version != versions[name]:
                raise ValueError('snapshot changed before install')
            updated = dict(target.functions)
            for slot, donor in plans[name].items():
                # 拷贝已被行为票支持的同伴函数；不是从健康代码标签表恢复。
                updated[slot] = before[donor.name][slot]
                changes.append({'subject': name, 'slot': slot, 'donor': donor.name,
                                'old_digest': function_digest(before[name][slot]),
                                'new_digest': function_digest(updated[slot]),
                                'negative_voters': quorum(ballots, contexts[name, slot], registry, False),
                                'donor_positive_voters': quorum(ballots, contexts[donor.name, slot], registry)})
            target.functions = updated
            target.version += 1
    after = {c.name: probe(c) for c in cells}
    return {'changes': changes, 'unresolved': unresolved,
            'scheduling_quorum': order is not None,
            'behaviour_after': {name: audit(rows) for name, rows in after.items()},
            'classifications': [[n, s, v] for (n, s), v in status.items()],
            'ballots': [asdict(b) for b in ballots], 'inspections': inspections,
            'calls': sum(c.calls for c in cells)}
