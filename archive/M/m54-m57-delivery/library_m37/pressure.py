"""预先声明的范围外与回退反证：结果不进入主实验调参。"""
from fractions import Fraction as F
from random import Random
from library_m12.core import Decision,compile_judge
from .core import Queen,NotLicensed,probe_packet,Budget,digest
from .world import World
from .identity import posterior,project


def setup():
    w=World();q=Queen();q.attach(w.port());q.review(0,True)
    return q,w


def exercise_rollback(q,w,base_tick=40):
    rows={}
    q.book.clock=base_tick
    if not q.valid():q.review(base_tick,True)
    prior=q._judge
    good=compile_judge((0,0,0))
    def bad_everywhere(p):
        r=good(p);return Decision(r.value+1,r.used)
    rows['bad_candidate_rejected']=(not q.propose_judgment(bad_everywhere,[probe_packet(1)]) and q._judge is prior)
    def latent(p):
        r=good(p);return Decision(r.value+(1 if p.target=='teacup' else 0),r.used)
    accepted=q.propose_judgment(latent,[probe_packet(1)])
    rows['latent_false_confidence_before_counterexample']=q.valid()
    before=q._judge
    out=q.act('teacup',2,base_tick+1,True)
    failed=out['executed'] and w.positions['teacup']!=2
    rolled=q._judge is prior and q.rollback_count==1 and not q.valid()
    blocked=[]
    for path in ('act','execute','decide','predict'):
        beforemoves=len(w.moves)
        try:
            if path in ('act','execute'):
                r=getattr(q,path)('apple',3,base_tick+2)
                ok=not r['executed']
            else:
                getattr(q,path)(probe_packet(3));ok=False
        except NotLicensed:ok=True
        blocked.append(ok and len(w.moves)==beforemoves)
    q.book.clock=base_tick+3
    q.review(base_tick+3,True)
    restored=q.act('teacup',1,base_tick+4)['executed'] and w.positions['teacup']==1
    rows['tentative_accepted']=accepted
    rows['later_error_observed']=failed
    rows['automatic_rollback']=rolled
    rows['all_four_entries_blocked']=all(blocked)
    rows['revalidated_future_restored']=restored
    rows['same_lived_queen']=id(q)==q._initial_id
    return rows


def run():
    q,w=setup()
    rows=exercise_rollback(q,w)
    rows['rollback_trace']=q.book.export()
    q,w=setup();w.gain=2
    q.act('apple',4,1)
    out=q.review(1,True)
    rows['outside_gain_abstains']=out['status']=='unresolved' and not q.valid()
    rows['outside_gain_hypotheses']=out.get('hypotheses')
    q,w=setup();w.cross_drift=True
    q.act('apple',2,1);out=q.review(1,True)
    rows['cross_object_drift_abstains']=out['status']=='unresolved' and not q.valid()
    q,w=setup();w.nonlinear=True
    out=q.review(1,True)
    rows['nonlinear_sensor_abstains']=out['status']=='unresolved' and not q.valid()
    # 未测的未来条件：有限验证不能提前看到杯子分支。
    # 匹配传感-动作并不保证历史身份：两候选公开数据完全相同。
    witness={'commands':[2],'deltas':[2],'endpoint':[3,3]}
    same=[dict(witness,author='self',id=1,refs=[1]),dict(witness,author='other',id=2,refs=[99])]
    rows['action_correct_identity_half']=posterior(witness,[project(v) for v in same])
    # 身份标签/引用/指纹全部对调，投影字节不变，真实作者评分字段也不入算法。
    projected=[project(v) for v in same]
    altered=[dict(v,author='fake',id=999,refs=[-1],fingerprint='x') for v in same]
    rows['metadata_and_graph_no_leak']=projected==[project(v) for v in altered]
    # 错误而自洽的外部参照：不声称本原型已可认证元核和现实测量的真伪。
    rows['remaining_trust']=['task_contract','calibration_anchors','port_semantics',
                             'meta_reviewer','history_custody','allowed_transition_family']
    return rows
