"""评估器持有目标，学习接口只收数值；挑战结果不决定抽象或计划。"""
from itertools import product
from .engine import run, CHECK_DOMAIN, FUTURE
from .synthesis import (Fuel, OutOfFuel, compile_plan, compile_program, digest, fit,
                        learn_macros, learn_normalized_macros, learn_plan, macro_branch, nodes, tuple_tree)
import json


def bases():
    return (lambda x:x*x, lambda x:x*(x-1)//2, lambda x:x*abs(x))


def curriculum():
    rows=[]
    for group,(base,cs) in enumerate(zip(bases(),((-2,-1,0,1),(-1,0,1,2),(-1,0,1,2)))):
        for c in cs:
            rows.append(({'family':group,'offset':c},lambda x,g=base,c=c:g(x)+c))
    return rows


def assess(fn,macros=None,plan=None,**kwargs):
    queen,result=run(fn,macros,plan,**kwargs)
    expected=[fn(x) for x in FUTURE]
    actual=[queen.decide(x) for x in FUTURE] if result['accepted'] else None
    result.update(future_inputs=list(FUTURE),future_expected=expected,future_actual=actual,
                  future_correct=0 if actual is None else sum(a==b for a,b in zip(actual,expected)),
                  all_future_correct=actual==expected)
    return result


def totals(rows):
    return {'tasks':len(rows),'accepted':sum(r['accepted'] for r in rows),
            'all_future_correct':sum(r['accepted'] and r['all_future_correct'] for r in rows),
            'future_cases':len(FUTURE)*len(rows),'future_correct':sum(r['future_correct'] for r in rows),
            'refutations':sum(r['refutations'] for r in rows),
            'at_least_two_refutations_then_success':sum(r['accepted'] and r['refutations']>=2 for r in rows),
            'candidate_attempts':sum(r['candidate_attempts'] for r in rows),
            'scalar_ops':sum(r['scalar_ops'] for r in rows),'oracle_calls':sum(r['oracle_calls'] for r in rows)}


def course_study():
    rows=[]
    for meta,fn in curriculum():
        result=assess(fn)
        result['evaluation_only_task']=meta; rows.append(result)
    # 不传未来成绩、名字、源码；仅采用前已准许的实际程序。
    manifest=[{'accepted':r['accepted'],'expression':r['expression']} for r in rows]
    macros,macro_rows=learn_macros(manifest)
    return {'summary':totals(rows),'rows':rows,'macros':macro_rows,
            'grammar_before':[],'grammar_after':list(macros)},macros


def pilot_study(macros):
    profile=[]; pilot=[]
    for family,g in enumerate(bases()):
        for d in (-1,2):
            # 全采用前域只作为计划训练数据；从不读取最终挑战。
            fn=lambda x,g=g,d=d:g(2*x+1)+d
            examples=tuple((x,fn(x)) for x in CHECK_DOMAIN)
            entry={}
            for name,body in macros.items():
                fuel=Fuel(200000)
                expr=macro_branch(name,body,examples,fuel)
                entry[name]={'fit':expr is not None,'attempts':fuel.attempts,
                             'scalar_ops':fuel.scalar_ops,'expression':expr}
            profile.append(entry)
            pilot.append({'evaluation_only_task':{'family':family,'d':d},'examples':examples,'routes':entry})
    selected=learn_plan(profile,tuple(macros))
    default=tuple(macros)
    def plan_cost(order):
        cost=0; solved=0
        for row in profile:
            for name in order:
                cost+=row[name]['attempts']
                if row[name]['fit']:
                    solved+=1; break
        return {'solved':solved,'cost':cost}
    return {'selected':selected,'default_order':list(default),
            'default_profile_cost':plan_cost(default),'learned_profile_cost':plan_cost(selected['order']),
            'profiles':pilot,'profile_oracle_calls':len(CHECK_DOMAIN)*len(pilot),
            'profile_candidate_attempts':sum(z['attempts'] for row in profile for z in row.values()),
            'profile_scalar_ops':sum(z['scalar_ops'] for row in profile for z in row.values()),
            'learned_source':compile_plan(selected['order']).source,
            'default_source':compile_plan(default).source,
            'plan_changed':list(default)!=selected['order']}


def transfer_study(macros,pilot,variants=('learned','default','reverse','no_macros','plain_json')):
    plans={'learned':compile_plan(pilot['selected']['order']),
           'default':compile_plan(tuple(macros)),'reverse':compile_plan(tuple(reversed(macros)))}
    learned=plans['learned']
    def plain(examples,library,budget=200000):
        copied=tuple(tuple(row) for row in json.loads(json.dumps(examples)))
        copied_macros={name:tuple_tree(body) for name,body in json.loads(json.dumps(library)).items()}
        return learned(copied,copied_macros,budget)
    plain.fingerprint=learned.fingerprint
    plans['plain_json']=plain
    rows={name:[] for name in variants}
    tasks=[]
    for family,g in enumerate(bases()):
        for a,b,d in product((2,3),(-3,4),(-2,1)):
            tasks.append(({'family':family,'a':a,'b':b,'d':d},lambda x,g=g,a=a,b=b,d=d:g(a*x+b)+d))
    for name in variants:
        for meta,fn in tasks:
            result=assess(fn, None if name=='no_macros' else macros,
                          None if name=='no_macros' else plans[name])
            result['evaluation_only_task']=meta; rows[name].append(result)
        print('transfer',name,totals(rows[name]),flush=True)
    return {'summaries':{name:totals(rs) for name,rs in rows.items()},'rows':rows,
            'frozen_grammar_key':digest(macros),'frozen_plan_key':learned.fingerprint}


def boundary_study(macros,plan):
    spike=lambda x:x*x+int(x==17)
    with_guard=assess(spike,macros,plan,guard=True)
    without_guard=assess(spike,macros,plan,guard=False)
    hidden=lambda x:x*x+int(x==71)
    unseen=assess(hidden,macros,plan,guard=True)
    # 同样的低信息情况下，在同一已声明枚举上分配更大预算。
    samples=((0,0),(1,1),(-1,1),(-2,4))
    budgets=[1,7,16,64,256]
    allocations=[{'budget':n,**fit(samples,budget=n)} for n in budgets]
    # 明确的反例遗忘循环，与学习器压力任务分开，不冒充自主发现。
    candidates=[lambda x:x,lambda x:1-x,lambda x:0]
    traces={}
    for retain in (False,True):
        evidence=[]; entries=[]
        for i in range(6):
            index=next((j for j,fn in enumerate(candidates) if all(fn(x)==y for x,y in evidence)),None)
            if index is None: break
            cex=next(((x,0) for x in (0,1) if candidates[index](x)!=0),None)
            entries.append({'candidate_index':index,'evidence':list(evidence),'counterexample':cex})
            if cex is None: break
            evidence=evidence+[cex] if retain else [cex]
        traces['retain' if retain else 'forget']=entries
    # 不可靠oracle完全一致地报错：不可仅靠内部重复判断揭露。
    wrong=assess(lambda x:x*x+1,macros,plan)
    wrong['true_square_future_errors']=sum(y!=x*x for x,y in zip(FUTURE,wrong['future_actual'])) if wrong['accepted'] else None
    return {'spike17_with_guard':with_guard,'spike17_without_guard':without_guard,
            'latent71':unseen,'budget_allocations':allocations,'forgetting_counterexample':traces,
            'wrong_reference':wrong}


def summarize(course,pilot,transfer,boundary):
    correct=['learned','default','reverse','plain_json']
    return {'M21':course['summary'],
            'M22':{'learned_operators':len(course['macros']),
                   'operator_definitions':[m['definition'] for m in course['macros']],
                   'spike17_guard_accepted':boundary['spike17_with_guard']['accepted'],
                   'spike17_guard_future_correct':boundary['spike17_with_guard']['all_future_correct'],
                   'spike17_no_guard_accepted':boundary['spike17_without_guard']['accepted']},
            'M23':{'plan_changed':pilot['plan_changed'],'plans_examined':pilot['selected']['plans_examined'],
                   'pilot_cost_before':pilot['default_profile_cost'],'pilot_cost_after':pilot['learned_profile_cost'],
                   'profile_candidate_attempts':pilot['profile_candidate_attempts'],
                   'profile_scalar_ops':pilot['profile_scalar_ops'],'profile_oracle_calls':pilot['profile_oracle_calls'],
                   'transfer':transfer['summaries'],
                   'plain_equal':transfer['rows'].get('learned')==transfer['rows'].get('plain_json')},
            'M24':{'latent71_accepted':boundary['latent71']['accepted'],
                   'latent71_errors':[x for x,y,z in zip(FUTURE,boundary['latent71']['future_actual'] or [],boundary['latent71']['future_expected']) if y!=z],
                   'wrong_reference_errors':boundary['wrong_reference']['true_square_future_errors'],
                   'finite_budget_remains':True,'metaconstructors_fixed':True}}


def adapt_representation(course,initial_macros):
    first=pilot_study(initial_macros)
    result={'initial_grammar':course['macros'],'initial_pilot':first,'changed':False}
    if first['selected']['pilot_solved']<6:
        inputs=[{'accepted':r['accepted'],'expression':r['expression']} for r in course['rows']]
        new_macros,new_rows=learn_normalized_macros(inputs,CHECK_DOMAIN)
        second=pilot_study(new_macros)
        result['alternative_grammar']=new_rows;result['alternative_pilot']=second
        old_key=(-first['selected']['pilot_solved'],first['selected']['pilot_candidate_cost'])
        new_key=(-second['selected']['pilot_solved'],second['selected']['pilot_candidate_cost'])
        if new_key<old_key:
            result['changed']=True;result['chosen_constructor']='subterms_plus_normalized_whole'
            course['macros']=new_rows;course['grammar_after']=list(new_macros)
            return new_macros,second,result
    result['chosen_constructor']='subterms'
    return initial_macros,first,result


def supplement_large_seed():
    """主参数冻结后的补充强基线；不回流调参。"""
    def larger(examples,unused,budget=200000):
        return fit(examples,budget=budget,maximum=25,constants=tuple(range(-4,5)))
    larger.fingerprint=digest({'supplement':'seed25_constants_m4_p4'})
    rows=[]
    for family,g in enumerate(bases()):
        for a,b,d in product((2,3),(-3,4),(-2,1)):
            fn=lambda x,g=g,a=a,b=b,d=d:g(a*x+b)+d
            r=assess(fn,{},larger)
            r['evaluation_only_task']={'family':family,'a':a,'b':b,'d':d}; rows.append(r)
    return {'registered_in_initial_contract':False,'max_nodes':25,'constants':list(range(-4,5)),
            'summary':totals(rows),'rows':rows,'used_to_train_or_select':False}
