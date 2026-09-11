"""M40审查后的新路径。旧M37源码不变；固定元核仍是明确前提。"""
from dataclasses import asdict
import json
from library_m37.core import Queen as BaseQueen,Book,Budget,BudgetExceeded
from library_m37.identity import posterior as compatible


class EvidenceBook(Book):
    def append(self,kind,source,data,refs=(),deps=()):
        if kind=='intention_memory':
            # 不接收评估器给出的绝对位置、位移或真实作者；只保存事前发令副本。
            if len(refs)!=1:raise ValueError('one prior action is required')
            record=self.ledger.records[refs[0]]
            if record.kind!='queen_action':raise ValueError('not an issued action')
            issued=json.loads(record.body)['data']['issued']
            data={'commands':[issued]}
        return super().append(kind,source,data,refs,deps)


class Queen(BaseQueen):
    def __init__(self,method='library'):
        super().__init__(method)
        self.book=EvidenceBook()  # 一次初始化，此后生命周期不替换账本。

    def _historical_frame(self,budget):
        if self.last_action in self.book.ledger.invalid:return None,None
        return super()._historical_frame(budget)

    def _environment_from_history(self,budget):
        if self.last_outcome in self.book.ledger.invalid or self.last_action in self.book.ledger.invalid:
            return None,None
        return super()._environment_from_history(budget)

    def review(self,tick,force=False):
        result=super().review(tick,force)
        if not result or result['status']!='accepted':return result
        # 区分真实支持与引用：过去错误判断可供反思，不因此成为当前许可前提。
        roots=set(result['probe_refs'])
        for k in result['read_refs']:
            if self.book.ledger.records[k].kind in ('queen_action','self_probe','calibration','control_probe'):
                roots.add(k)
        # 环境推断使用了结果内容时，不能只登记它指向的动作。
        control_probed=any(self.book.ledger.records[k].kind=='control_probe' for k in result['probe_refs'])
        if not control_probed and self.last_outcome is not None:roots.add(self.last_outcome)
        budget=Budget(**result['budget'])
        try:
            budget.spend('reads',len(roots));budget.spend('comparisons',len(roots))
        except BudgetExceeded:
            self.invalidate('dependency binding budget exhausted')
            result.update(status='dependency_budget_reject',budget=asdict(budget));return result
        if any(k in self.book.ledger.invalid for k in roots):
            self.invalidate('withdrawn evidence cannot support current permission')
            result.update(status='withdrawn_support_reject',budget=asdict(budget));return result
        old_assumption=self.assumption
        self.assumption=self.book.append('supported_assumption','queen',
            {'support_complete_for_declared_review_inputs':True,'support':sorted(roots)},
            refs=tuple(sorted(roots)),deps=(old_assumption,*sorted(roots)))
        self.license=self.book.append('permission','queen',
            {'revision':self.revision,'scope':'M41 bounded task; explicit observation dependencies'},
            refs=(self.last_review,),deps=(self.assumption,))
        self.bindings=self.binding()
        result['budget']=asdict(budget);result['proof_support']=sorted(roots)
        self.book.append('proof_rebind','queen',
            {'support':sorted(roots),'current_permission':self.license,'budget':asdict(budget)},
            refs=(self.last_review,),deps=(self.assumption,))
        return result


def project(candidate):
    # 历史输入只保留可观察的命令；合流后只有终态则没有可区分命令。
    if 'commands' not in candidate:return {}
    values=candidate['commands']
    if not isinstance(values,list) or not values or any(type(x) is not int for x in values):
        raise ValueError('integer commands required')
    return {'commands':values[:]}


def posterior(witness,candidates):
    if len(candidates)!=2:raise ValueError('two-candidate attribution scope')
    return compatible(project(witness),[project(c) for c in candidates])


def revisit(queen,witness_ref,candidates):
    budget=Budget();witness=None
    if queen.method not in ('recent','masked'):witness=queen.read(witness_ref,budget)
    clean=[project(c) for c in candidates]
    if witness is None:
        result={'status':'ambiguous','probabilities':[.5,.5],'possible':[0,1]}
    else:
        budget.spend('comparisons',len(clean));result=posterior(witness,clean)
    result.update(budget=asdict(budget),public_packet=clean,witness_used=witness is not None,
                  scope='issued-command compatibility under explicit custody and two-candidate assumptions',
                  falsifier='contradictory authenticated commands or loss of custody; imitation remains ambiguous')
    ref=queen.book.append('attribution_review','queen',result,
                         refs=(witness_ref,) if witness is not None else ())
    queen.identity_beliefs.append({'review':ref,'result':result})
    return result


def install():
    # 显式适配入口，非自主写入新元算法；不会改变旧文件或旧runner的默认行为。
    from library_m37 import study
    study.Queen=Queen
    study.revisit=revisit
    study.project=project
    study.posterior=posterior
    return study

_BASE_ROLLBACK=None

def integrated_rollback(queen,world,base_tick=40):
    result=_BASE_ROLLBACK(queen,world,base_tick)
    if not isinstance(queen,Queen):return result
    roots=queen.audit_history[-1]['proof_support']
    k=next(k for k in roots if queen.book.ledger.records[k].kind=='calibration')
    queen.book.clock=base_tick+5
    queen.book.revoke(k,'calibration evidence withdrawn after lived rollback')
    result['withdrawn_support_closes_permission']=not queen.valid()
    from library_m37.core import NotLicensed,probe_packet
    blocked=[]
    for name in ('act','execute','decide','predict'):
        count=len(world.moves)
        try:
            if name in ('act','execute'):ok=not getattr(queen,name)('apple',3,base_tick+6)['executed']
            else:getattr(queen,name)(probe_packet(8));ok=False
        except NotLicensed:ok=True
        blocked.append(ok and len(world.moves)==count)
    result['withdrawn_support_blocks_four_entries']=all(blocked)
    queen.book.clock=base_tick+7
    review=queen.review(base_tick+7,True)
    out=queen.act('teacup',4,base_tick+8,True)
    result['withdrawal_reproof_future_correct']=(review['status']=='accepted' and out['executed'] and world.positions['teacup']==4)
    return result

_ORIGINAL_INSTALL=install

def install():
    global _BASE_ROLLBACK
    study=_ORIGINAL_INSTALL()
    from library_m37 import pressure
    if _BASE_ROLLBACK is None:_BASE_ROLLBACK=pressure.exercise_rollback
    pressure.exercise_rollback=integrated_rollback
    return study
