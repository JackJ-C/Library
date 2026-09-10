"""检查器只回馈首个反例；最终未见挑战完全在评估层。"""
from dataclasses import dataclass
from .synthesis import (compile_program, digest, evaluate, expand, fit, nodes, source,
                         tuple_tree)

CHECK_DOMAIN=tuple(sorted(range(-24,25),key=lambda x:(abs(x),x)))
FUTURE=tuple(x for x in range(-80,81) if x not in CHECK_DOMAIN)


class CounterexampleTeacher:
    def __init__(self,get_value,domain=CHECK_DOMAIN):
        self._get_value=get_value; self.domain=tuple(domain); self.calls=0
    def initial(self,x):
        self.calls+=1
        return self._get_value(x)
    def check(self,program):
        visits=0
        for x in self.domain:
            y=self._get_value(x); self.calls+=1; visits+=1
            if program(x)!=y: return (x,y),visits
        return None,visits


class Queen:
    def __init__(self,macros=None,plan=None):
        self.macros={} if macros is None else dict(macros)
        self.plan=plan
        self.program=None; self.proposal=None; self.certificate=None
        self.evidence={}; self.events=[]; self.revision=0; self.inconsistent=False
    def decide(self,x):
        if self.inconsistent or self.program is None or self.certificate is None: raise RuntimeError('no current certificate')
        if self.certificate['program']!=self.program.fingerprint: raise RuntimeError('binding changed')
        if self.certificate['evidence']!=digest(tuple(self.evidence.items())): raise RuntimeError('evidence changed')
        return self.program(x)
    def observe(self,x,y):
        if type(x) is not int or type(y) is not int: raise ValueError('integers required')
        if x in self.evidence:
            if self.evidence[x] != y:
                self.certificate=None; self.inconsistent=True; self.events.append({'kind':'inconsistent','x':x,'y':y})
                raise ValueError('contradictory evidence')
            return False
        self.evidence[x]=y; self.certificate=None
        self.events.append({'kind':'observation','x':x,'y':y})
        return True
    def propose(self,budget=200000):
        if self.inconsistent: raise ValueError('new epoch required after contradiction')
        evidence=tuple(self.evidence.items())
        answer=(fit(evidence,budget=budget) if self.plan is None else
                self.plan(evidence,self.macros,budget=budget))
        if answer['expression'] is not None:
            self.proposal=compile_program(answer['expression'],self.macros)
        return answer
    def commit(self,proposal,domain):
        # 仅在外部check成功之后由run触发；不能认证错误的外部规范。
        if self.inconsistent: raise ValueError('cannot certify inconsistent evidence')
        if not all(proposal(x)==y for x,y in self.evidence.items()): raise ValueError('old counterexample regressed')
        self.program=proposal; self.revision+=1
        self.certificate={'program':proposal.fingerprint,'evidence':digest(tuple(self.evidence.items())),
                          'domain':list(domain),'scope':'finite_checked_domain_only'}


def run(get_value,macros=None,plan=None,budget=200000,round_limit=12,guard=False):
    teacher=CounterexampleTeacher(get_value); queen=Queen(macros,plan)
    same_instance=id(queen)
    for x in (0,1): queen.observe(x,teacher.initial(x))
    rounds=[]; accepted=False; total_attempts=0; total_scalar=0; previous=None
    for i in range(round_limit):
        reserved=len(queen.evidence) if guard and previous is not None else 0
        if budget <= reserved:
            rounds.append({'round':i,'status':'budget_exhausted_before_search'})
            break
        answer=queen.propose(budget-reserved)
        total_attempts+=answer['attempts']; total_scalar+=answer['scalar_ops']
        program=queen.proposal if answer['expression'] is not None else None
        entry={'round':i,'evidence':list(queen.evidence.items()),'search':answer,
               'certificate_before':queen.certificate}
        if program is None and guard and previous is not None:
            # 给定的等值守卫构造器：其数值、残差及具体谓词由反例实例化。
            body=previous.lowered
            patches=[]
            for x,y in queen.evidence.items():
                delta=y-evaluate(body,x)
                if delta:
                    body=('add',body,('mul',('c',delta),('eq',('x',),('c',x))))
                    patches.append({'x':x,'delta':delta})
            program=compile_program(body,{})
            entry['representation_extension']={'kind':'equality_residual','patches':patches,
                'base_search_status':answer['status'],'given_metarule':True}
            # 补丁不是免费搜索，计入统一上限；预算满时不偷偷超额继续。
            if answer['attempts']+len(patches) > budget:
                entry['status']='budget_exhausted_before_patch'; rounds.append(entry); break
            total_attempts+=len(patches)
        if program is None:
            entry['status']=answer['status']; rounds.append(entry); break
        if not all(program(x)==y for x,y in queen.evidence.items()):
            raise AssertionError('candidate regresses a retained counterexample')
        cex,visits=teacher.check(program)
        entry.update(expression=program.expression,lowered=program.lowered,source=program.source,
                     fingerprint=program.fingerprint,compressed_nodes=nodes(program.expression),
                     expanded_nodes=nodes(program.lowered),checker_visits=visits,
                     counterexample=cex)
        if cex is None:
            queen.commit(program,teacher.domain); accepted=True
            entry['status']='accepted'; rounds.append(entry); break
        x,y=cex
        if program(x)==y: raise AssertionError('not a genuine counterexample')
        entry['status']='refuted'; entry['old_prediction']=program(x)
        queen.observe(x,y)
        queen.events.append({'kind':'revoked_proposal','program':program.fingerprint,
                             'counterexample':(x,y)})
        if queen.certificate is not None: raise AssertionError('stale certificate')
        previous=program; rounds.append(entry)
    return queen,{'accepted':accepted,'rounds':rounds,'evidence':list(queen.evidence.items()),
        'expression':queen.program.expression if accepted else None,
        'lowered':queen.program.lowered if accepted else None,
        'source':queen.program.source if accepted else None,'events':queen.events,
        'refutations':sum(r.get('status')=='refuted' for r in rounds),
        'oracle_calls':teacher.calls,'candidate_attempts':total_attempts,
        'scalar_ops':total_scalar,'same_instance':id(queen)==same_instance,
        'deployed_revisions':queen.revision,'plan_fingerprint':None if plan is None else plan.fingerprint,
        'certificate':queen.certificate}
