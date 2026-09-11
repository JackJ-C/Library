"""主实验与反证。故障真值仅在此评估层持有，不传入 Queen.review。"""
from collections import Counter
from functools import lru_cache
from fractions import Fraction as F
from itertools import product
from random import Random
from .core import (PROGRAMS, Decision, Frame, Packet, Reading, Queen, Worker,
                   compile_judge, fault_mask, frame_json, locus, reference, require)

SENSORS = tuple(product((-2, -1, 1, 2), (-7, 0, 5)))


@lru_cache(maxsize=1024)
def make_case(seed, novel=False, stage='learn'):
    rng = Random(seed)
    width = rng.choice((2, 3)) if novel else 1
    subject = ('novel-' if novel else stage + '-') + str(rng.randrange(10**9))
    other = 'other-' + str(rng.randrange(10**9))
    base = rng.randint(-5000, 5000) if novel else rng.randint(-30, 30)
    start = rng.randrange(1000, 10000) if novel else rng.randrange(20, 100)
    gap = rng.randrange(3, 20)
    # 各时期中心不同；真值由生成结构给出，非候选解释器算出。
    centers = {(subject, start): base - 19, (subject, start+gap): base + 13,
               (other, start-2): base - 200, (other, start+gap+2): base + 300}
    rows = []
    for (owner, epoch), center in centers.items():
        step = rng.randint(1, 7)
        for j in range(-width, width+1):
            rows.append(Reading('r'+str(len(rows)), owner, epoch, F(center+j*step)))
    rng.shuffle(rows)
    return Packet(subject, tuple(rows)), {0: F(base+13), 1: F(base-19)}


def materialize(packet, emit):
    return Packet(packet.target, tuple(Reading(r.key, r.subject, r.epoch, emit(r.value)) for r in packet.rows))


def audit_packets():
    return tuple(make_case(4000+i, stage='probe')[0] for i in range(8))


def validation_packets():
    return tuple(make_case(80000+i, stage='validation')[0] for i in range(4))


def setup(program, sensor, age, seed):
    worker = Worker(*sensor)
    queen = Queen(compile_judge(program), age)
    for i in range(4):
        packet, _ = make_case(10000+seed*31+i)
        queen.decide(materialize(packet, worker.emit))
    return queen, worker


def run_one(program, sensor, age, seed, keep_trace=False):
    queen, worker = setup(program, sensor, age, seed)
    q_object, meta_binding = id(queen), queen.review.__func__
    q0 = queen._judge
    w0 = worker.decoder
    # 相同信息的普通序列日志，而非少给信息的弱对照。
    plain, pw = setup(program, sensor, age, seed)
    pdiag = plain.review(pw.probe, pw.recalibrate, audit_packets(), validation_packets(), 'plain')
    diag = queen.review(worker.probe, worker.recalibrate, audit_packets(), validation_packets())
    require(id(queen) == q_object and queen.review.__func__ is meta_binding, 'binding/trust boundary changed')
    comparable = ('status', 'locus', 'qmask', 'worker_fault', 'self_queries', 'worker_queries', 'patches')
    require(all(diag[k] == pdiag[k] for k in comparable), 'same-information log differs')
    expected_mask = fault_mask(program, age)
    expected_w = sensor != (1, 0)
    expected = locus(expected_mask, expected_w)
    correct = diag['status'] == 'accepted' and diag['locus'] == expected and diag['qmask'] == list(expected_mask)
    q_changed = queen._judge is not q0
    w_changed = worker.decoder != w0
    locality = q_changed == any(expected_mask) and w_changed == expected_w
    q1, w1 = queen._judge, worker.decoder
    counts = [0, 0, 0, 0]
    regressions, bits = 0, []
    gain, bias = sensor  # 只用于独立评估，不给诊断器。
    for i in range(32):
        packet, expected_values = make_case(1000000+seed*997+i, novel=True)
        truth = expected_values[age]
        correct_flags = []
        for decoder in (w0, w1):
            a, b = decoder
            observations = materialize(packet, lambda v: a*(gain*v+bias)+b)
            correct_flags.extend(judge(observations).value == truth for judge in (q0, q1))
        counts = [n+int(ok) for n, ok in zip(counts, correct_flags)]
        regressions += correct_flags[0] and not correct_flags[3]
        bits.append(sum(1 << j for j, ok in enumerate(correct_flags) if ok))
    # 缺少自身历史时不允许猜；随后允许通过真实自身调用补回信息。
    stripped, sw = setup(program, sensor, age, seed)
    blocked = stripped.review(sw.probe, sw.recalibrate, audit_packets(), validation_packets(), 'worker_only', 0)
    require(blocked['status'] == 'abstain' and stripped.revision == 0, 'missing self evidence guessed')
    resumed, rw = setup(program, sensor, age, seed)
    reacquired = resumed.review(rw.probe, rw.recalibrate, audit_packets(), validation_packets(), 'worker_only', 8)
    require(reacquired['status'] == 'accepted' and reacquired['locus'] == expected, 'self probe recovery failed')
    row = {'program': list(program), 'sensor': list(sensor), 'contract_age': age, 'layout_seed': seed,
           'expected_locus': expected, 'predicted_locus': diag['locus'], 'qmask': diag['qmask'],
           'localized': correct, 'locality': locality, 'queen_changed': q_changed, 'worker_changed': w_changed,
           'old_judge': q0.fingerprint, 'new_judge': q1.fingerprint,
           'self_queries': diag['self_queries'], 'worker_queries': diag['worker_queries'],
           'without_history_self_queries': reacquired['self_queries'], 'without_history_zero_budget': blocked['status'],
           'plain_equal': True, 'four_corner_correct_of_32': counts, 'outcome_bitmasks': bits,
           'regressions': regressions, 'patches': diag['patches'], 'candidates': diag['candidates']}
    if keep_trace:
        row['audit_trace'] = diag
        row['historical_frames_after_review'] = [frame_json(f) for f in queen.history]
    return row


def main_study():
    rows, summaries = [], Counter()
    by_locus = {}
    for age in (0, 1):
        for program in PROGRAMS:
            for sensor in SENSORS:
                for seed in range(8):
                    # 四种根类各保留一份详尽链，其余保存逐次结果与可重建输入。
                    expected = locus(fault_mask(program, age), sensor != (1, 0))
                    keep = expected not in by_locus
                    row = run_one(program, sensor, age, seed, keep)
                    rows.append(row)
                    group = by_locus.setdefault(expected, Counter())
                    group['runs'] += 1
                    group['correct_locus'] += row['localized']
                    group['only_self_fully_correct'] += row['four_corner_correct_of_32'][1] == 32
                    group['only_worker_fully_correct'] += row['four_corner_correct_of_32'][2] == 32
                    group['both_fully_correct'] += row['four_corner_correct_of_32'][3] == 32
                    summaries['runs'] += 1
                    summaries['correct_locus'] += row['localized']
                    summaries['locality_pass'] += row['locality']
                    summaries['before_correct'] += row['four_corner_correct_of_32'][0]
                    summaries['after_correct'] += row['four_corner_correct_of_32'][3]
                    summaries['regressions'] += row['regressions']
                    summaries['extra_self_queries'] += row['self_queries']
                    summaries['reacquired_self_queries'] += row['without_history_self_queries']
                    summaries['plain_equal'] += row['plain_equal']
        print('completed contract', age, 'runs', len(rows), flush=True)
    return {'summary': dict(summaries), 'by_locus': {k: dict(v) for k, v in by_locus.items()}, 'rows': rows}


def pressure_study():
    # 主实验冻结后的反例；不回流扩展主语法。
    base = compile_judge((0, 0, 0))
    def latent(packet):
        d = base(packet)
        return Decision(d.value + int(packet.target.startswith('novel-')), d.used)
    latent.fingerprint = 'outside-grammar-latent'
    q, w = Queen(latent, 0), Worker(1, 0)
    for i in range(4):
        q.decide(make_case(10000+i)[0])
    d = q.review(w.probe, w.recalibrate, audit_packets(), validation_packets())
    failed = sum(q.decide(p, False).value != truth[0]
                 for p, truth in (make_case(1000000+i, novel=True) for i in range(32)))
    require(d['locus'] == 'healthy' and failed == 32, 'latent model-bound counterexample')
    # 外部错误不在仿射族中，元核应拒绝而不是误改自己的代码。
    q = Queen(base, 0)
    for i in range(4):
        q.decide(make_case(10000+i)[0])
    bad = q.review(lambda x: x*x, lambda a, b: (_ for _ in ()).throw(AssertionError('must not install')),
                   audit_packets(), validation_packets())
    require(bad['status'] == 'abstain' and bad['worker_fault'] is None, 'nonlinear must abstain')
    # 破坏的是被明确保留为可信的元核；此例不能获得整体自证。
    broken, bw = setup((1, 0, 0), (1, 0), 0, 0)
    def broken_meta(*args, **kwargs):
        return {'status': 'accepted', 'locus': 'healthy'}
    broken.review = broken_meta
    bad_claim = broken.review()
    kernel_failures = sum(broken.decide(p, False).value != truth[0]
                          for p, truth in (make_case(1000000+i, novel=True) for i in range(32)))
    require(bad_claim['locus'] == 'healthy' and kernel_failures > 0, 'trusted kernel counterexample')
    # 最终输出相同，但正确修复所属组件不同。
    indistinguishable = []
    for x in range(-16, 17):
        a = (x + 0) + 7  # W 正常，Q 错
        b = (x + 7) + 0  # W 错，Q 正常
        require(a == b, 'output equivalence')
        indistinguishable.append([x, a, b])
    return {'latent_queen': {'diagnosis': d['locus'], 'challenge_failures_of_32': failed},
            'nonlinear_worker': {'status': bad['status'], 'queen_revision': q.revision},
            'broken_meta_kernel': {'diagnosis': bad_claim['locus'], 'challenge_failures_of_32': kernel_failures},
            'output_equivalent_pair': indistinguishable,
            'separated_probes': {'self_only_outputs': [7, 0], 'worker_only_outputs': [0, 7]}}
