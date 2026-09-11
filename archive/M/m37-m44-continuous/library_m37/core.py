"""连续对象、可再观察切片、诊断与执行门禁。只读取公开经历/探测。

复用 M12 的真实判断函数、候选重放及 Worker 校准；复用 M8 的引用/依赖账本。
固定元审查核和可信模拟器接口是显式前提，不是恶意同进程隔离。
"""
from dataclasses import dataclass, asdict
from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import json
from library_m12.core import (Queen as TaskQueen, Packet, Reading, Decision, Frame,
    PROGRAMS, compile_judge, simulate, frame_json, frame_load, reference, fault_mask)
from library_m8.core import Ledger


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


class BudgetExceeded(RuntimeError): pass
class NotLicensed(RuntimeError): pass


@dataclass
class Budget:
    reads: int = 0
    probes: int = 0
    comparisons: int = 0
    bytes_read: int = 0
    max_reads: int = 24
    max_probes: int = 6
    max_comparisons: int = 6000

    def spend(self, name, count=1):
        if getattr(self, name) + count > getattr(self, 'max_' + name):
            raise BudgetExceeded(name)
        setattr(self, name, getattr(self, name) + count)


class Book:
    """旧 Ledger 原记录不变；可见时刻和预算在新统一入口执行。"""
    def __init__(self):
        self.ledger = Ledger()
        self.clock = 0

    def append(self, kind, source, data, refs=(), deps=()):
        return self.ledger.add(kind, source, {'time': self.clock, 'data': data},
                               refs=tuple(dict.fromkeys(refs)), deps=tuple(dict.fromkeys(deps)))

    def read(self, key, budget, horizon=None, plain=False):
        if type(key) is not int or not 0 <= key < len(self.ledger.records):
            raise ValueError('unknown historical slice')
        horizon = len(self.ledger.records)-1 if horizon is None else horizon
        if key > horizon:
            raise ValueError('future evidence')
        budget.spend('reads')
        rec = self.ledger.records[key]
        # 同信息 JSON 对照实际经过序列化；返回内容相同。
        body = json.loads(rec.body)
        if plain:
            body = json.loads(json.dumps(body, ensure_ascii=False))
        budget.bytes_read += len(rec.body.encode())
        return body.get('data',body)

    def revoke(self, root, reason):
        if root is not None and root not in self.ledger.invalid:
            self.ledger.revoke(root, reason)

    def export(self):
        return self.ledger.export()


def packet_from_views(views, previous, target, tick):
    """M12 原生 Packet；每位置三读数，中位数去除对称采样扰动。"""
    rows = []
    previous = views if previous is None else previous
    for epoch, item in ((tick*2, previous), (tick*2+1, views)):
        for obj in ('apple','teacup'):
            for j, v in enumerate(item[obj]):
                rows.append(Reading(f'{epoch}:{obj}:{j}', obj, epoch, F(v)))
    return Packet(target, tuple(rows))


def probe_packet(tick):
    # 公共任务探测，主体/时期/值可区分；不是隐藏故障标签或身份码。
    rows=[]
    for subject,epoch,values in (('apple',0,(1,4,9)),('apple',1,(12,15,22)),
                                 ('teacup',-1,(-15,-11,-8)),('teacup',2,(31,37,45))):
        for j,value in enumerate(values):
            rows.append(Reading(f'd:{tick}:{subject}:{epoch}:{j}',subject,epoch,F(value)))
    return Packet('apple',tuple(rows))


def centered(view):
    return {o: int(sorted(map(F, view[o]))[1]) for o in ('apple','teacup')}


class Queen(TaskQueen):
    """同一个对象从开始到结束。故障/事件类型不进入审查接口。"""
    METHODS=('library','plain','recent','masked','no_revision','recalibrate')

    def __init__(self, method='library'):
        if method not in self.METHODS: raise ValueError('method')
        super().__init__(compile_judge((0,0,0)),0)
        self.method=method
        self.book=Book()
        self.hypotheses={'judge':list(PROGRAMS),'worker0':[-2,0,2],
                         'worker1':[-2,0,2],'environment':[-1,1]}
        self.dynamics=None
        self.license=None
        self.assumption=None
        self.bindings=None
        self.last_views=None
        self.last_action=None
        self.last_outcome=None
        self.last_review=None
        self.audit_history=[]
        self.identity_beliefs=[]
        self.control_model={}
        self.snapshots=[]
        self.pending=True
        self.last_audit_tick=-100
        self._port=None
        self._initial_id=id(self)
        self._recent=None
        self.transaction=None
        self.rollback_count=0
        self.binding_changes=0
        self.unresolved=[]

    def attach(self, port):
        if self._port is not None and self._port is not port:
            raise ValueError('cannot replace the lived world')
        self._port=port

    def binding(self):
        # 仅门禁核验当前绑定；绝不提供给原因推断或匿名历史归属。
        return (id(self._judge), tuple(self._port.decoders()), self.dynamics)

    def valid(self):
        return (self.license is not None and self.license not in self.book.ledger.invalid
                and self.bindings == self.binding())

    def invalidate(self, reason):
        self.book.revoke(self.assumption,reason)
        self.pending=True
        if self.transaction is not None:
            prior=self.transaction;self.transaction=None
            self._judge=prior['judge']
            self.license=None;self.bindings=None
            self.rollback_count+=1
            self.book.append('rollback','queen',{'reason':reason,'restored_prior_program':True},
                             (prior['proposal_ref'],))

    def decide(self, packet, remember=True):
        if not self.valid():
            self.invalidate('execution precondition no longer supported')
            raise NotLicensed('no current evidence-backed permission')
        return super().decide(packet,remember)

    def diagnostic_judgment(self, packet, budget):
        # 无许可时只允许有预算的无外部副作用诊断计算。
        budget.spend('probes')
        result=super().decide(packet,True)
        ref=self.book.append('self_probe','queen',frame_json(Frame(packet,result)))
        return frame_json(Frame(packet,result)),ref

    def read(self,key,budget,horizon=None):
        return self.book.read(key,budget,horizon,self.method=='plain')

    def sense(self):
        packet=self._port.sense()
        refs=[]
        for i, view in enumerate(packet):
            refs.append(self.book.append('worker_view',f'worker{i}',view))
        return packet,refs

    def act(self, obj, target, tick, future=False):
        self.book.clock=tick
        before,refs=self.sense()
        current=before[0]['decoded']
        packet=packet_from_views(current,self.last_views,obj,tick)
        self.last_views=current
        try:
            d=self.decide(packet)
        except NotLicensed:
            self.book.append('blocked','queen',{'task':obj,'target':target,'reason':'invalid permission'},refs)
            return {'executed':False,'action':None,'target':target,'object':obj,'future':future}
        if d.value.denominator != 1:
            self.invalidate('nonintegral spatial judgment')
            self.book.append('self_probe','queen',frame_json(Frame(packet,d)),refs)
            return {'executed':False,'action':None,'target':target,'object':obj,'future':future}
        action=((target-int(d.value))*self.dynamics)%5
        intention={'object':obj,'target':target,'estimated_position':int(d.value),
                   'assumed_gain':self.dynamics,'issued':action,
                   'frame':frame_json(Frame(packet,d)), 'future':future}
        aid=self.book.append('queen_action','queen',intention,refs)
        self._port.move(obj,action)
        after,postrefs=self.sense()
        outcome={'object':obj,'issued':action,'target':target,
                 'before':[v['decoded'] for v in before],
                 'after':[v['decoded'] for v in after],
                 'action_ref':aid,'future':future}
        oid=self.book.append('outcome','world_observation',outcome,(aid,*postrefs))
        self.last_action,self.last_outcome=aid,oid
        # 检测使用自身实际结果，不接受故障发生时间/种类通知。
        predicted=int(d.value)
        suspicious=(d.value != reference(packet,0))
        for i in (0,1):
            b,a=centered(before[i]['decoded']),centered(after[i]['decoded'])
            suspicious |= a[obj]%5 != target%5
            other='teacup' if obj=='apple' else 'apple'
            suspicious |= a[other] != b[other]
            suspicious |= any(a[o] != centered(after[0]['decoded'])[o] for o in a)
        if suspicious: self.invalidate('prediction/action/observation disagreement')
        return {'executed':True,'action':action,'object':obj,'target':target,
                'action_ref':aid,'outcome_ref':oid,'future':future}

    def _q_candidates(self, data, budget):
        frame=frame_load(data)
        result=[]
        for p in PROGRAMS:
            budget.spend('comparisons')
            if simulate(p,frame.packet)==frame.decision: result.append(p)
        return result

    def _historical_frame(self,budget):
        if self.method=='recent':
            if self._recent and self._recent[1]=='queen_action':
                return self._recent[2]['frame'],self._recent[0]
            return None,None
        if self.method in ('masked','recalibrate'): return None,None
        # 根据当前不确定性选择自己的实际作用记录，而不是固定读最后一条。
        if self.last_action is not None:
            row=self.read(self.last_action,budget)
            return row['frame'],self.last_action
        return None,None

    def _environment_from_history(self,budget):
        if self.method in ('masked','recalibrate') or self.last_outcome is None:
            return None,None
        if self.method=='recent':
            if not self._recent or self._recent[1]!='outcome':return None,None
            row=self._recent[2]
        else:row=self.read(self.last_outcome,budget)
        stamp=json.loads(self.book.ledger.records[self.last_outcome].body).get('time')
        if stamp != self.book.clock: return None,None
        a=row['issued']
        if not a: return None,None
        obj=row['object']; other='teacup' if obj=='apple' else 'apple'
        possibilities=[]
        for g in (-1,1):
            budget.spend('comparisons')
            if all((centered(row['after'][i])[obj]-centered(row['before'][i])[obj])%5 == a*g%5
                   and centered(row['after'][i])[other]==centered(row['before'][i])[other]
                   for i in (0,1)):
                possibilities.append(g)
        return possibilities,row.get('action_ref')

    def review(self,tick,force=False):
        if not(force or self.pending or tick-self.last_audit_tick>=3): return None
        budget=Budget(); refs=[]; prior=self.hypotheses
        self._recent=None
        if self.method=='recent' and self.book.ledger.records:
            k=len(self.book.ledger.records)-1
            self._recent=(k,self.book.ledger.records[k].kind,self.read(k,budget))
        outcome={'tick':tick,'method':self.method,'status':'unresolved','patches':[],
                 'read_refs':[],'probe_refs':[],'revision_before':self.revision}
        try:
            frame,ref=self._historical_frame(budget)
            qH=self._q_candidates(frame,budget) if frame is not None else list(PROGRAMS)
            if ref is not None: refs.append(ref)
            # 若历史未唯一支持所需修订，主动取得当前自身行为，不把旧模型当正确答案。
            masks={fault_mask(p,0) for p in qH}
            if len(masks)!=1 or self.method=='recalibrate' or not self.valid():
                probe,ref=self.diagnostic_judgment(probe_packet(tick),budget)
                qH=self._q_candidates(probe,budget); refs.append(ref); outcome['probe_refs'].append(ref)
            masks={fault_mask(p,0) for p in qH}
            bH=[]
            for i in (0,1):
                budget.spend('probes')
                values=self._port.calibrate(i,(0,3))
                ref=self.book.append('calibration',f'worker{i}',{'anchors':[0,3],'observed':values})
                refs.append(ref);outcome['probe_refs'].append(ref)
                options=[]
                for b in (-2,0,2):
                    budget.spend('comparisons')
                    if values==[b,3+b]: options.append(b)
                bH.append(options)
            gH,ref=self._environment_from_history(budget)
            if ref is not None: refs.append(ref)
            if gH is None or len(gH)!=1 or self.method=='recalibrate':
                budget.spend('probes')
                control=self._port.control_probe()
                ref=self.book.append('control_probe','queen',control)
                refs.append(ref);outcome['probe_refs'].append(ref)
                gH=[]
                for g in (-1,1):
                    budget.spend('comparisons')
                    if control['deltas']==[g%5,g%5] and control['cross_deltas']==[0,0]: gH.append(g)
            H={'judge':qH,'worker0':bH[0],'worker1':bH[1],'environment':gH}
            self.hypotheses=H
            # 旧假说在仍相容时保留；真正矛盾才重新开放该坐标。
            reopened=[]
            for k,values in H.items():
                retained=[v for v in prior[k] if v in values]
                if retained: H[k]=retained
                elif prior[k]: reopened.append(k)
            outcome['reopened_coordinates']=reopened
            outcome['hypotheses']=H
            outcome['prior_hypotheses']=prior
            determined=(bool(qH) and len(masks)==1 and all(len(h)==1 for h in bH) and len(gH)==1)
            if not determined:
                self.invalidate('observations do not support one permissible revision')
                self.unresolved.append({'tick':tick,'hypotheses':H})
                outcome['reason']='model_conflict_or_ambiguous'
            else:
                qbad=any(next(iter(masks)))
                offset=[h[0] for h in bH]; gain=gH[0]
                needed=[]
                if qbad:needed.append('queen_judge')
                needed += [f'worker{i}' for i,b in enumerate(offset) if b]
                if self.dynamics!=gain:needed.append('environment_model')
                outcome['diagnosed']=needed
                if self.method=='no_revision' and self.revision>0 and needed:
                    self.invalidate('revision disabled by control condition')
                    outcome.update(status='revision_disabled')
                else:
                    old_judge=self._judge;old_gain=self.dynamics
                    old_decoders=self._port.decoders();undo=[]
                    self.invalidate('recheck before approval')
                    # 候选只改诊断所要求的组件，正常绑定不重置。
                    if qbad:self._judge=compile_judge((0,0,0));self.binding_changes+=1
                    for i,b in enumerate(offset):
                        if b:undo.append(self._port.recalibrate(i,b))
                    self.dynamics=gain
                    # 与诊断分离的公开小样验证，不读取独立未来任务。
                    test=probe_packet(tick+100000)
                    d=TaskQueen.decide(self,test,False)
                    ok=(d.value==reference(test,0) and self._port.validate_calibration())
                    if not ok:
                        self._judge=old_judge;self.dynamics=old_gain
                        for f in reversed(undo):f()
                        outcome.update(status='validation_reject')
                    else:
                        if needed:
                            self.revision+=1
                            self.snapshots.append((old_judge,old_gain,old_decoders))
                        self.assumption=self.book.append('assumption','queen',
                            {'stable_until_counterevidence':True,'supported_family':'M37',
                             'controls':{'apple':gain,'teacup':gain},
                             'falsifier':'new own IO or paired displacement/calibration disagrees'},refs)
                        self.license=self.book.append('permission','queen',
                            {'revision':self.revision,'scope':'bounded tasks; stationary between reviews'},
                            refs,(self.assumption,))
                        self.bindings=self.binding(); self.pending=False
                        self.control_model={'apple':gain,'teacup':gain,'other_actor':'not controlled',
                                            'falsifier':'cross-object drift or changed paired response'}
                        outcome.update(status='accepted',patches=needed,revision_after=self.revision,
                                       actual_judge_binding_changed=self._judge is not old_judge,
                                       decoder_binding_changed=self._port.decoders()!=old_decoders,
                                       old_model_gain=old_gain,new_model_gain=gain)
                        # 推断结果随实际修订映射到新版本，不重置整个 Queen 或历史。
                        self.hypotheses={'judge':[(0,0,0)],'worker0':[0],'worker1':[0],
                                         'environment':[gain]}
        except BudgetExceeded as exc:
            self.invalidate('review budget exhausted')
            outcome['reason']='budget:'+str(exc)
        outcome['read_refs']=list(dict.fromkeys(refs))
        outcome['budget']=asdict(budget)
        outcome['same_instance']=id(self)==self._initial_id
        self.last_audit_tick=tick
        references=tuple(refs)+(() if self.last_review is None else (self.last_review,))
        self.last_review=self.book.append('review','queen',outcome,references)
        self.audit_history.append(outcome)
        return outcome

    def execute(self,obj,target,tick):
        return self.act(obj,target,tick)

    def predict(self,packet):
        return self.decide(packet,False)

    def propose_judgment(self,candidate,validation_packets):
        """统一有许可候选入口；复核后暂存新程序，反证触发撤销与回退。

        这是有限样本检验而非全域证明；故意潜伏候选可通过后再被未来反证。
        """
        if not self.valid():raise NotLicensed('cannot revise from invalid permission')
        checks=[]
        for p in validation_packets:
            checks.append(candidate(p).value==reference(p,0))
        proposal=self.book.append('proposal','queen',{'checks':checks,'sample_scope_only':True},
                                  (self.license,))
        if not all(checks):
            self.book.append('proposal_rejected','queen',{'reason':'counterexample'},(proposal,))
            return False
        previous=self._judge
        self.assumption=self.book.append('assumption','queen',{'candidate_sample_validated':True},
                                         (proposal,),(self.assumption,))
        self.license=self.book.append('permission','queen',{'tentative':True},
                                      (proposal,),(self.assumption,))
        self._judge=candidate;self.binding_changes+=1;self.revision+=1
        self.bindings=self.binding()
        self.transaction={'judge':previous,'proposal_ref':proposal}
        return True
