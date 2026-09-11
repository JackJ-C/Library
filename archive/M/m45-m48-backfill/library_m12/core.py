"""真实判断函数的有限修订；诊断不读故障标签或传感器真参数。"""
from dataclasses import dataclass, asdict
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
from statistics import median
from typing import Callable, Optional, Tuple
import json

PROGRAMS = tuple(product(range(2), range(2), range(3)))


def require(ok, text):
    if not ok:
        raise ValueError(text)


@dataclass(frozen=True)
class Reading:
    key: str
    subject: str
    epoch: int
    value: F


@dataclass(frozen=True)
class Packet:
    target: str
    rows: Tuple[Reading, ...]


@dataclass(frozen=True)
class Decision:
    value: F
    used: Tuple[str, ...]


@dataclass(frozen=True)
class Frame:
    packet: Packet
    decision: Decision


def packet_json(packet):
    return {'target': packet.target, 'rows': [
        [r.key, r.subject, r.epoch, str(r.value)] for r in packet.rows]}


def frame_json(frame):
    return {'packet': packet_json(frame.packet), 'value': str(frame.decision.value),
            'used': list(frame.decision.used)}


def frame_load(data):
    p = data['packet']
    return Frame(Packet(p['target'], tuple(Reading(k, s, t, F(v)) for k, s, t, v in p['rows'])),
                 Decision(F(data['value']), tuple(data['used'])))


def compile_judge(program):
    """只编译封闭语法常量，不拼接外部输入；不是任意代码安全沙箱。"""
    require(program in PROGRAMS and all(type(i) is int for i in program), 'invalid program')
    scope, age, aggregate = program
    selection = '[r for r in packet.rows if r.subject == packet.target]' if scope == 0 else 'list(packet.rows)'
    extreme = 'max' if age == 0 else 'min'
    reducer = ('median', 'min', 'max')[aggregate]
    source = ('def judge(packet):\n'
              '    rows = ' + selection + '\n'
              '    epoch = ' + extreme + '(r.epoch for r in rows)\n'
              '    chosen = [r for r in rows if r.epoch == epoch]\n'
              '    answer = ' + reducer + '([r.value for r in chosen])\n'
              '    return Decision(answer, tuple(sorted(r.key for r in chosen)))\n')
    env = {'__builtins__': {'list': list, 'min': min, 'max': max, 'tuple': tuple, 'sorted': sorted},
           'median': median, 'Decision': Decision}
    exec(compile(source, '<finite-queen-judge>', 'exec'), env)
    fn = env['judge']
    fn.fingerprint = sha256(source.encode()).hexdigest()
    return fn


def simulate(program, packet):
    """与生成函数分开实现的候选解释器。"""
    scope, age, reducer = program
    groups = {}
    for row in packet.rows:
        if scope == 1 or row.subject == packet.target:
            groups.setdefault(row.epoch, []).append(row)
    keys = sorted(groups)
    chosen = groups[keys[0] if age else keys[-1]]
    ordered = sorted(r.value for r in chosen)
    if reducer == 1:
        answer = ordered[0]
    elif reducer == 2:
        answer = ordered[-1]
    else:
        n = len(ordered)
        answer = ordered[n//2] if n % 2 else (ordered[n//2-1] + ordered[n//2]) / 2
    return Decision(answer, tuple(sorted(r.key for r in chosen)))


def reference(packet, age):
    """公开任务合同的可信参考；不是学习器自创的评价标准。"""
    matching = tuple(r for r in packet.rows if r.subject == packet.target)
    epochs = sorted({r.epoch for r in matching})
    chosen_epoch = epochs[0 if age else -1]
    values = sorted(r.value for r in matching if r.epoch == chosen_epoch)
    return (values[(len(values)-1)//2] + values[len(values)//2]) / 2


def fault_mask(program, age):
    return (program[0] != 0, program[1] != age, program[2] != 0)


def locus(qmask, worker):
    return 'both' if any(qmask) and worker else ('self' if any(qmask) else ('worker' if worker else 'healthy'))


def infer_programs(frames):
    return tuple(p for p in PROGRAMS if all(simulate(p, f.packet) == f.decision for f in frames))


class Worker:
    """物理测量机制不可变；允许修订本 Worker 内的仿射解码器。"""
    def __init__(self, gain, bias):
        self.__gain, self.__bias = F(gain), F(bias)
        self.decoder = (F(1), F(0))
        self.probes = 0

    def emit(self, value):
        a, b = self.decoder
        return a * (self.__gain * value + self.__bias) + b

    def probe(self, value):
        self.probes += 1
        return self.emit(value)

    def recalibrate(self, slope, offset):
        require(slope != 0, 'noninvertible measurement')
        old = self.decoder
        a, b = old
        self.decoder = (a / slope, (b - offset) / slope)
        def undo():
            self.decoder = old
        return undo


class Queen:
    """被修订的判断器属于此实例；review 的元审查算法仍是可信固定代码。"""
    def __init__(self, judge, age):
        require(age in (0, 1), 'invalid task contract')
        self._judge, self.age = judge, age
        self.history = []
        self.events = []
        self.revision = 0

    def decide(self, packet, remember=True):
        decision = self._judge(packet)
        if remember:
            self.history.append(Frame(packet, decision))
        return decision

    def review(self, probe_worker: Callable, install_worker: Callable,
               probe_packets, validation_packets, history_mode='full', self_budget=8):
        require(history_mode in ('full', 'plain', 'worker_only'), 'invalid history mode')
        require(type(self_budget) is int and self_budget >= 0, 'invalid self budget')
        # 诊断输入白名单：原输入、实际输出/读取集。指纹不用于推断代码身份。
        frames = list(self.history) if history_mode != 'worker_only' else []
        if history_mode == 'plain':
            frames = [frame_load(json.loads(json.dumps(frame_json(f)))) for f in frames]
        H = infer_programs(frames)
        used, extra = set(), 0
        while H and len({fault_mask(p, self.age) for p in H}) > 1 and extra < self_budget:
            best, best_score = None, 0
            for i, packet in enumerate(probe_packets):
                if i in used:
                    continue
                groups = {}
                for p in H:
                    d = simulate(p, packet)
                    groups[(d.value, d.used)] = groups.get((d.value, d.used), 0) + 1
                score = len(H)**2 - sum(n*n for n in groups.values())
                if score > best_score:
                    best, best_score = i, score
            if best is None:
                break
            used.add(best)
            packet = probe_packets[best]
            frames.append(Frame(packet, self.decide(packet)))
            extra += 1
            H = infer_programs(frames)
        anchors = (-4, 0, 9)
        answers = tuple(probe_worker(F(x)) for x in anchors)
        slope, offset = (answers[2] - answers[0]) / 13, answers[1]
        affine = slope != 0 and all(y == slope*x + offset for x, y in zip(anchors, answers))
        masks = {fault_mask(p, self.age) for p in H}
        result = {'status': 'abstain', 'locus': 'unknown', 'qmask': None,
                  'worker_fault': (slope != 1 or offset != 0) if affine else None,
                  'self_queries': extra, 'worker_queries': 3, 'candidates': len(H),
                  'witnesses': [frame_json(f) for f in frames],
                  'worker_evidence': [[x, str(y)] for x, y in zip(anchors, answers)],
                  'patches': [], 'revision_before': self.revision}
        if len(masks) != 1 or not affine:
            self.events.append(result)
            return result
        qmask = next(iter(masks))
        wbad = slope != 1 or offset != 0
        result.update(qmask=list(qmask), locus=locus(qmask, wbad))
        old_judge = self._judge
        # 使用兼容解释和合同构造最小槽位修改，不读取当前函数内部的故障标记。
        proposal = tuple((0, self.age, 0)[j] if qmask[j] else H[0][j] for j in range(3))
        candidate = compile_judge(proposal) if any(qmask) else old_judge
        if not all(candidate(p).value == reference(p, self.age) for p in validation_packets):
            result['status'] = 'validation_reject'
            self.events.append(result)
            return result
        undo = install_worker(slope, offset) if wbad else lambda: None
        check = tuple(probe_worker(F(x)) for x in (37, -23))
        result['worker_queries'] += 2
        if check != (F(37), F(-23)):
            undo()
            result['status'] = 'validation_reject'
            self.events.append(result)
            return result
        self._judge = candidate
        if not all(self.decide(p, remember=False).value == reference(p, self.age) for p in validation_packets):
            self._judge = old_judge
            undo()
            result['status'] = 'validation_reject'
            self.events.append(result)
            return result
        if any(qmask):
            self.revision += 1
            result['patches'].append({'owner': 'self', 'binding': 'Queen._judge',
                                     'slots': [j for j, bad in enumerate(qmask) if bad]})
        if wbad:
            result['patches'].append({'owner': 'worker', 'binding': 'Worker.decoder',
                                     'slope': str(slope), 'offset': str(offset)})
        result.update(status='accepted', revision_after=self.revision,
                      old_judge=old_judge.fingerprint, new_judge=self._judge.fingerprint)
        self.events.append(result)
        return result
