"""R1/R2: bounded functional self-model and executable acquisition-policy revision.
No network, task reward, hidden fault label or actor id is an inference input.
The M54 Queen is subclassed, not claimed to have acquired this wrapper by itself.
"""
from collections import Counter
from itertools import product
from pathlib import Path
from hashlib import sha256
import json
import sys

VENDOR = Path(__file__).resolve().parents[1] / 'vendor'
sys.path.insert(0, str(VENDOR))
from library_m54.queen import Queen as MQueen, NotLicensed
from library_m54.grammar import compile_tree
from library_m54.world import World, Port

P = 7
PRIOR = tuple(product(range(1,7), range(7), range(7), range(1,7)))
# Public probe vocabulary, not hidden mechanism names or correct answers.
QUERIES = (('self',0),('motor',0),('cal',0),('cal',3),
           ('self',1),('motor',1),('self',2),('motor',2))
FEATURES = ('diversity', 'balance', 'cost', 'index')


def canonical(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',',':'))


def model_probe(h, query):
    s,b0,b1,k=h;kind,a=query
    if kind=='self': return (s*a % P,)
    if kind=='cal': return ((a+b0)%P,(a+b1)%P)
    return (s*a%P, k*s*a%P, k*s*a%P)


def expression(ast):
    if isinstance(ast,int): return str(ast)
    if isinstance(ast,str):
        if ast not in FEATURES: raise ValueError('unknown score feature')
        return ast
    op,a,b=ast
    if op not in ('+','-','*'): raise ValueError('unknown score operator')
    return '('+expression(a)+op+expression(b)+')'


def score_program(ast):
    text='def rank(diversity,balance,cost,index):\n    return '+expression(ast)+'\n'
    scope={'__builtins__':{}}
    exec(compile(text,'<R bounded score>','exec'),scope)
    f=scope['rank'];f.source=text;f.ast=ast
    return f


def choose(H, available, policy):
    rows=[];ops=0
    for i,q in enumerate(available):
        c=Counter(model_probe(h,q) for h in H);ops+=len(H)
        vals=(len(c),len(H)**2-sum(n*n for n in c.values()),3 if q[0]=='motor' else 1,i)
        rows.append((policy(*vals),-i,q,vals))
    selected=max(rows,key=lambda r:r[:2])
    return selected[2],ops,{'query':list(selected[2]),'features':list(selected[3]),
                           'scores':[[list(r[2]),r[0]] for r in rows]}


def learn_in_model(ast, worlds):
    """Explicitly counterfactual planning in declared finite model, not real probes.
    Generator and evaluator are fixed. It does not implement recursive self-improvement.
    """
    policy=score_program(ast);calls=ops=0
    for htrue in worlds:
        H=PRIOR;available=list(QUERIES)
        while len(H)>1 and available:
            q,n,_=choose(H,available,policy);ops+=n+len(H);calls+=1
            value=model_probe(htrue,q)
            H=tuple(h for h in H if model_probe(h,q)==value);available.remove(q)
        if len(H)!=1:raise RuntimeError('diagnostic basis failed')
    return calls,ops


class Queen(MQueen):
    def __init__(self, seed=0, method='library'):
        super().__init__(seed,method)
        self.offsets=[0,0]  # Provisional decoding only for diagnostic trials; no permission.
        self.self_options=tuple(range(1,7));self.H=PRIOR
        self.self_permission=None;self.policy=score_program(0);self.policy_history=[]
        self.own_models=[];self.r_cost=Counter();self.review_log=[];self.old_explanations=[]
        self.action_program=None;self.plan_bound=None;self.options_bound=None;self.local_support=[];self.self_source=None
        self.r_origin=id(self);self.r_book=id(self.ledger)
        self.meta_rounds=[];self.pending_self_counterexample=None

    def r_valid(self):
        return (super().valid() and self.self_permission is not None and
                self.self_permission not in self.ledger.invalid and self.action_program is self.plan_bound
                and self.action_program is not None and self.self_options==self.options_bound)

    def withdraw(self,reason,refs=()):
        # Actual evidence remains; obsolete licenses, not all historical references, are revoked.
        if self.permission is not None and self.permission not in self.ledger.invalid:
            self.ledger.revoke(self.permission,reason)
        self.old_explanations.append({'version':self.version,'H':list(self.H),'reason':reason,'refs':list(refs)})
        return self.add('R_mismatch',{'reason':reason,'version':self.version},refs=refs)

    def probe(self,port,query):
        kind,a=query;self.r_cost['probe_requests']+=1
        if kind=='self':
            i=self.add('R_internal_intention',{'requested':a})
            result=self._emit(a)
            k=self.add('R_internal_receipt',{'requested':a,'issued':result},refs=(i,))
            self.r_cost['emitter_calls']+=1
            return (result,),[i,k]
        if kind=='cal':
            r=port.calibrate(a)
            if set(r)!={'anchor','readings'} or r['anchor']!=a:raise ValueError('calibration schema')
            k=self.add('R_calibration',r)
            self.r_cost['calibration_scalars']+=len(r['readings'])
            return tuple(r['readings']),[k]
        # M54 trial actually calls this Queen's emitter and appends an intention/observation.
        before=port.sense();e=super().trial(port,0,a,'R_probe')
        after=self.read(e['observation'])['after']
        ds=tuple((after['workers'][j][0]-before['workers'][j][0])%P for j in range(2))
        self.r_cost['emitter_calls']+=1;self.r_cost['motor_probes']+=1
        return (e['issued'],)+ds,[e['intention'],e['observation']]

    def diagnose(self,port):
        H=PRIOR;available=list(QUERIES);support=[];own=[];cal=[];motor=[];steps=[]
        if self.pending_self_counterexample is not None:
            old=self.read(self.pending_self_counterexample)
            query=('self',old['requested'])
            value,keys=self.probe(port,query);support+=keys;own+=keys
            H=tuple(h for h in H if model_probe(h,query)==value)
            steps.append({'query':list(query),'observed':list(value),'before':len(PRIOR),'after':len(H),
                          'evidence':keys,'reason':'retest previous own counterexample from history'})
            if H:self.pending_self_counterexample=None
        previous={'self_options':list(self.self_options),'world_tree':self.tree,'offsets':self.offsets[:],
                  'version':self.version}
        while len(H)>1 and available and len(steps)<10:
            query,ops,choice=choose(H,available,self.policy);self.r_cost['candidate_ops']+=ops+len(H)
            value,keys=self.probe(port,query);support+=keys
            if query[0]=='self':own+=keys
            elif query[0]=='motor':own+=keys;motor+=keys
            else:cal+=keys
            old_count=len(H);H=tuple(h for h in H if model_probe(h,query)==value)
            steps.append(dict(choice,observed=list(value),before=old_count,after=len(H),evidence=keys))
            available.remove(query)
        self.H=H
        if len(H)!=1:
            self.withdraw('diagnostic model insufficient',support)
            record={'status':'unresolved','candidates':len(H),'steps':steps,'previous':previous}
            self.review_log.append(record);return record
        s,b0,b1,g=H[0];oldfn=self.action_program
        self.self_options=(s,);self.offsets=[b0,b1]
        self.self_permission=self.add('R_own_model',{'multiplier_options':[s],
             'prediction_scope':'issued=requested*s mod7; stationary until contradicted',
             'falsifier':'a later own receipt differs'},deps=tuple(dict.fromkeys(own)))
        self.calibration=self.add('R_worker_model',{'offsets':[b0,b1]},deps=tuple(dict.fromkeys(cal)))
        self.scope=self.add('R_world_model',{'gain':g},deps=tuple(dict.fromkeys(motor)))
        self.tree=('gain',g);self.function=self.bound=compile_tree(self.tree)
        # Actual task program embeds the learned own-effect and world-effect, not oracle params.
        inv=pow(s*g,-1,P)
        source=f'def plan(position,goal):\n    return ((goal-position)*{inv})%7\n'
        ns={'__builtins__':{}};exec(compile(source,'<R learned inverse>','exec'),ns)
        self.action_program=ns['plan'];self.action_program.source=source
        self.plan_bound=self.action_program;self.options_bound=self.self_options
        self.permission=self.add('R_task_permission',{'source':source,'version':self.version+1},
             deps=(self.self_permission,self.calibration,self.scope))
        self.version+=1;self.local_support=list(dict.fromkeys(support))
        record={'status':'adopted','steps':steps,'previous':previous,'identified':list(H[0]),
                'task_source':source,'policy_source':self.policy.source,'version':self.version,
                'actual_plan_binding_changed':oldfn is not self.action_program,'support':self.local_support}
        self.own_models.append(self.self_permission);self.review_log.append(record)
        self.add('R_review',record,refs=tuple(self.local_support)+tuple(self.own_models[-2:-1]))
        return record

    def decide(self,before,obj,goal):
        if not self.r_valid():raise NotLicensed('R license invalid')
        decoded=self.decode(before)
        if decoded[0]!=decoded[1]:raise NotLicensed('Worker disagreement')
        action=propose(self.self_options,self.tree[1],decoded[0][obj],goal)
        if action is None or action!=self.action_program(decoded[0][obj],goal):
            raise NotLicensed('self model / compiled plan disagreement')
        return action

    def step(self,port,obj,goal,learn=True):
        before=port.sense()
        try:request=self.decide(before,obj,goal)
        except NotLicensed as exc:
            return {'executed':False,'reason':str(exc),'predicted_probability':None}
        p=self.decode(before)[0][obj];expected=self.self_options[0]*request%P
        delta=self.function(p,self.decode(before)[0][1-obj],obj,self.last,expected)
        forecast=self.add('R_prospective_self',{'requested':request,'predicted_issued':expected,
             'predicted_position':(p+delta)%P,'goal':goal,'version':self.version},
             refs=(self.self_permission,self.permission))
        e=super().trial(port,obj,request,'R_task')
        after=self.read(e['observation'])['after'];decoded=self.decode(after)
        mismatch=(e['issued']!=expected or decoded[0]!=decoded[1] or decoded[0][obj]!=(p+delta)%P)
        row={'executed':True,'request':request,'issued':e['issued'],'predicted_issued':expected,
             'observed':after['workers'],'before':before['workers'],'object':obj,'goal':goal,
             'mismatch':mismatch,'forecast':forecast,'intention':e['intention'],'observation':e['observation']}
        if mismatch and learn:
            if e['issued']!=expected:self.pending_self_counterexample=e['intention']
            self.withdraw('own forecast or Worker observation mismatch',(forecast,e['intention'],e['observation']))
        return row

    def retrospective(self):
        prior=self.old_explanations[-1] if self.old_explanations else None
        row={'old':prior,'current_self_options':list(self.self_options),'current_world_tree':self.tree,
             'claim':'old expectation conflicts with recorded observations, not erased',
             'historical_authorship':'not inferred from version names or instance ids'}
        self.add('R_retrospective',row,refs=tuple(prior['refs']) if prior else ())
        return row

    def evolve(self,seed, frozen_proposer=False):
        """Try bounded recursion: the incumbent scoring function also orders which
        candidate improvement programs receive full simulated evaluation.
        Proposal grammar, feature construction and acceptance test remain fixed.
        Counterfactual frozen-proposer arm holds candidate set and budget constant.
        """
        from random import Random
        rng=Random(seed)
        observed=[tuple(r['identified']) for r in self.review_log if r['status']=='adopted'][-1:]
        if not observed:return None
        before=self.policy;terms=[0,1]+list(FEATURES);pool=[before.ast]
        for _ in range(12):
            pool.append((rng.choice(('+','-')),rng.choice(terms),rng.choice(terms)))
        unique=list({canonical(p):p for p in pool}.values())
        # Candidate descriptors come only from the declared hypothesis space and
        # source execution, not held-out success, hidden parameters or labels.
        meta_features=[];descriptor_ops=0
        for i,ast in enumerate(unique):
            q,n,detail=choose(PRIOR,list(QUERIES),score_program(ast));descriptor_ops+=n
            d,b,c,_=detail['features']
            meta_features.append((d,b,c+len(expression(ast)),i))
        proposer=score_program(0) if frozen_proposer else before
        order=sorted(range(len(unique)), key=lambda i:(-proposer(*meta_features[i]),i))
        selected=order[:6]  # Same six full candidate evaluations in every arm.
        scored=[]
        for index in selected:
            ast=unique[index];calls,ops=learn_in_model(ast,observed)
            scored.append((calls,ops,len(expression(ast)),canonical(ast),ast))
        scored.sort(key=lambda x:x[:4]);best=scored[0]
        old_score=learn_in_model(before.ast,observed)
        accept=best[:2]<old_score
        if accept:self.policy=score_program(best[4]);self.policy_history.append(self.policy.source)
        total_ops=sum(r[1] for r in scored)+old_score[1]+descriptor_ops
        self.r_cost['meta_simulation_ops']+=total_ops
        row={'training_diagnostics':len(observed),'old_source':before.source,'new_source':self.policy.source,
             'accepted':accept,'actual_policy_rebound':self.policy is not before,
             'old_score':list(old_score),'selected_score':list(best[:2]),
             'search_candidates':len(unique),'fully_evaluated':len(selected),
             'meta_simulation_ops':total_ops,'proposer_source':proposer.source,
             'proposed_order':selected,'proposed_asts':unique,
             'candidate_scores':[[expression(r[4]),r[0],r[1]] for r in scored],
             'uses_parent_policy_to_order_candidates':not frozen_proposer,
             'generator_scope':'fixed AST proposals; parent program ranks evaluation order; no test result input'}
        self.meta_rounds.append(row);self.add('R_meta_revision',row,refs=tuple(self.own_models))
        return row


def propose(options, gain, position, goal):
    """A shared deliberation primitive; uncertainty is not filled with a default self."""
    actions={((goal-position)*pow(s*gain,-1,7))%7 for s in options}
    return next(iter(actions)) if len(actions)==1 else None
