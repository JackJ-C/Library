"""历史归属独立于功能成绩。身份推断只见白名单投影，不见作者/ID/图边。

本模块判断历史片段与当前控制端记住的作用轨迹是否相容。来源保管和
两候选中恰有一条自身经历是实验前提；相同行为/状态合流时不能强分。
"""
from dataclasses import asdict
import json
from .core import Budget,canonical


ALLOWED=('commands','deltas','endpoint')


def project(candidate):
    # 不保留ID、作者、时间标签、引用链、排序键或程序指纹。
    result={}
    for k in ALLOWED:
        if k not in candidate:continue
        v=candidate[k]
        if not isinstance(v,list) or not v or any(type(x) is not int for x in v):
            raise ValueError('only integer observable vectors are allowed')
        if k=='endpoint' and len(v)!=2:raise ValueError('two object positions required')
        result[k]=v[:]
    return result


def posterior(witness,candidates):
    if any(not project(c) for c in candidates):
        return {'status':'ambiguous','probabilities':[1/len(candidates)]*len(candidates),
                'possible':list(range(len(candidates)))}
    possibilities=[]
    for i,c in enumerate(candidates):
        visible=project(c)
        if all(k in witness and visible[k]==witness[k] for k in visible):
            possibilities.append(i)
    if not possibilities:
        return {'status':'inconsistent','probabilities':[None]*len(candidates),'possible':[]}
    probabilities=[(1/len(possibilities) if i in possibilities else 0.0) for i in range(len(candidates))]
    return {'status':'identified' if len(possibilities)==1 else 'ambiguous',
            'probabilities':probabilities,'possible':possibilities}


def revisit(queen,witness_ref,candidates):
    budget=Budget();witness=None
    if queen.method not in ('recent','masked'):
        witness=queen.read(witness_ref,budget)
    clean=[project(c) for c in candidates]
    if witness is None:
        result={'status':'ambiguous','probabilities':[0.5,0.5],'possible':[0,1]}
    else:
        budget.spend('comparisons',len(clean))
        result=posterior(witness,clean)
    result['budget']=asdict(budget)
    result['public_packet']=clean
    result['witness_used']=witness is not None
    result['scope']='compatibility with retained own efference under two-candidate custody'
    result['falsifier']='new authenticated action evidence contradicts the match; exact imitation keeps ambiguity'
    ref=queen.book.append('attribution_review','queen',result,
                         (witness_ref,) if witness is not None else ())
    queen.identity_beliefs.append({'review':ref,'result':result})
    return result


def build_case(queen,move,witness_ref,kind,rng,current_action=None):
    """评估器执行匹配的另一控制者轨迹。推断器看不到kind/作者/引用链。"""
    from .world import World
    before=move['before'];after=move['after'];obj=move['object'];cmd=move['command']
    delta=(after[obj]-before[obj])%5
    gain=(delta*pow(cmd,-1,5))%5 if cmd else 1
    gain=-1 if gain==4 else gain
    w={'commands':[cmd],'deltas':[delta],
       'endpoint':[after['apple'],after['teacup']]}
    other=World(before['apple'],before['teacup']);other.gain=gain
    if kind in ('distinct','anonymous'): commands=[(cmd+1)%5]
    elif kind=='changed':
        if current_action is None or current_action==cmd:return None
        commands=[current_action]
    elif kind=='identical':commands=[cmd]
    elif kind=='merge':commands=[(cmd+1)%5,4]
    else:raise ValueError('case kind')
    alternate_deltas=[]
    for a in commands:
        m=other.step(obj,a)
        alternate_deltas.append((m['after'][obj]-m['before'][obj])%5)
    alt={'commands':commands,'deltas':alternate_deltas,
         'endpoint':[other.positions['apple'],other.positions['teacup']]}
    if kind=='merge':
        w={'endpoint':w['endpoint']};alt={'endpoint':alt['endpoint']}
    data=[w,alt];truth=0
    if rng.randrange(2):data.reverse();truth=1
    for i,c in enumerate(data):
        c.update({'id':f'alias-{rng.randrange(10**9)}','author':'Queen' if i==1-truth else 'Worker',
                  'refs':[999-i],'fingerprint':'not-an-answer','time':rng.randrange(999)})
    return data,truth,{'other_executed_commands':commands,'other_final':dict(other.positions),
                       'self_actual_command':cmd,'same_start':before}
