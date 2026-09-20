"""R41 read-only independent implementation. Imports no Queen/learner/R37 modules.
Checks the finite traces, not runtime isolation or universal correctness.
"""
import hashlib
import json
import math
from fractions import Fraction
from random import Random
from statistics import mean
from collections import Counter

AV = ('mean','uncert','visits','gap')
TV = ('info','price','spread','order')
OPS = ('+','-','*','/')
INITIAL = {'ast': ['-','mean','uncert'], 'scale': 1.0}


def canon(x):
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


def hashed(x):
    return hashlib.sha256(canon(x).encode()).hexdigest()


def frozen(x):
    return tuple(map(frozen,x)) if isinstance(x,(list,tuple)) else x


def check(ok,msg):
    if not ok: raise ValueError(msg)


def equal(x,y,path='value'):
    if isinstance(x,(list,tuple)) and isinstance(y,(list,tuple)):
        check(len(x)==len(y),path+' length')
        for i,(a,b) in enumerate(zip(x,y)):equal(a,b,path+'/'+str(i))
    elif isinstance(x,dict) and isinstance(y,dict):
        check(set(x)==set(y),path+' keys')
        for k in x:equal(x[k],y[k],path+'/'+k)
    elif isinstance(x,float) or isinstance(y,float):
        check(isinstance(x,(int,float)) and isinstance(y,(int,float)) and math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-12),path+' float')
    else:check(x==y,path+' mismatch')


def size(t):return 1 if isinstance(t,(int,str)) else 1+size(t[1])+size(t[2])

def text(t):return str(t) if isinstance(t,(int,str)) else '('+text(t[1])+t[0]+text(t[2])+')'

def bundle(ast,scale):return {'ast':ast,'scale':scale,'key':hashed([ast,scale])}


def innovation(seed,phase,index,role):
    return int.from_bytes(hashlib.sha256(canon([seed,phase,index,role]).encode()).digest()[:8],'big')


def generate_pool(parent,seed,is_task=False):
    rng=Random(seed);variables=TV if is_task else AV
    def draw(depth):
        if depth==0 or rng.random() < (.35 if is_task else .4):
            return rng.choice((0,1,2,-1)+variables if is_task else variables+(0,1,2,-1))
        return (rng.choice(OPS),draw(depth-1),draw(depth-1))
    def change(t):
        if isinstance(t,(int,str)) or rng.random()<.3:return draw(2)
        side=(rng.randrange(2)+1) if is_task else rng.choice((1,2))
        parts=list(t);parts[side]=change(t[side]);return tuple(parts)
    seen={text(parent)};out=[parent];count=6 if is_task else 8
    for _ in range(100 if is_task else 1000):
        t=change(parent) if rng.random()<(.55 if is_task else .6) else draw(3 if is_task else 2)
        if size(t)>15 or text(t) in seen:continue
        seen.add(text(t));out.append(t)
        if len(out)==count:return out
    if not is_task:raise ValueError('allocator generation exhausted')
    return out


def allocator_pool(parent,seed):
    asts=generate_pool(parent['ast'],seed)
    rng=Random(seed^731)
    return [parent]+[bundle(a,rng.choice((.5,1.,2.))) for a in asts[1:]]


def bank(seed):
    outer=Random(seed);result=[]
    for _ in range(6):
        rng=Random(outer.randrange(1<<50)); masks=[]; prices=[]
        for q in range(12):
            nc=rng.choice((2,2,3,4,5))
            w=[rng.expovariate(1) for _ in range(nc)]
            label=rng.choices(range(nc),weights=w,k=16)
            masks.append([sum(1<<i for i in range(16) if label[i]==k) for k in range(nc)])
            prices.append(rng.randrange(1,10))
        for bit in range(4):
            masks.append([sum(1<<i for i in range(16) if ((i>>bit)&1)==v) for v in (0,1)])
            prices.append(rng.randrange(3,10))
        result.append({'problem':{'masks':masks,'prices':prices,'count':16},'identified':rng.randrange(16)})
    return result


def evaluate(t,features,mode,cost):
    key='allocation_ast_ops' if mode=='allocator' else 'ast_ops';cost[key]+=1
    if type(t) is int:return float(t) if mode=='allocator' else t*256
    if isinstance(t,str):return features[(AV if mode=='allocator' else TV).index(t)]
    a=evaluate(t[1],features,mode,cost);b=evaluate(t[2],features,mode,cost)
    if t[0]=='+':v=a+b
    elif t[0]=='-':v=a-b
    elif t[0]=='*':v=a*b if mode=='allocator' else a*b//256
    elif t[0]=='/':v=a/(abs(b)+.001) if mode=='allocator' else a*256//(abs(b)+1)
    else:raise ValueError('operator')
    cap=1e6 if mode=='allocator' else 10**9
    return max(-cap,min(cap,v))


def solve(problem,hidden,ast):
    masks,prices,n=problem['masks'],problem['prices'],problem['count']
    remaining=(1<<n)-1; available=list(range(len(masks)));trace=[];paid=0;cost=Counter()
    while remaining.bit_count()>1 and available:
        candidates=[]
        for q in available:
            z=[(m&remaining).bit_count() for m in masks[q]];total=remaining.bit_count()
            cost['feature_ops']+=len(z)+3
            f=((total**2-sum(v*v for v in z))*1024//(total**2),prices[q]*128,sum(v>0 for v in z)*128,q*16)
            if f[0]>0:candidates.append((evaluate(ast,f,'task',cost),-q,q,f))
        if not candidates:break
        _,_,q,f=max(candidates);value=next(i for i,m in enumerate(masks[q]) if m&(1<<hidden))
        before=remaining;remaining &= masks[q][value];available.remove(q);paid+=prices[q];cost['queries']+=1
        trace.append({'query':q,'value':value,'before':before,'after':remaining,'features':list(f),'price':prices[q]})
    check(remaining.bit_count()==1,'diagnostic did not separate')
    return paid,remaining,trace,cost


class Engine:
    def __init__(self,tasks,blocks):
        self.tasks=tasks;self.blocks=blocks;self.tc={};self.rc={};self.cost=Counter()
    def task(self,arm,j,k):
        self.cost['task_loss_requests']+=1;key=arm,j,k
        if key not in self.tc:
            cell=self.blocks[j][k];p,h=cell['problem'],cell['identified']
            price,H,trace,c=solve(p,h,self.tasks[arm])
            sig=[[v['query'],v['value'],v['price']] for v in trace]
            self.tc[key]=[price/(9*len(p['masks'])),sig]
            self.cost.update({'simulated_queries':c['queries'],'task_ast_ops':c['ast_ops'],
                              'task_feature_ops':c['feature_ops'],'simulated_query_price':price})
        else:self.cost['task_cache_hits']+=1
        return self.tc[key]
    def response(self,b,j):
        self.cost['intervention_requests']+=1;key=b['key'],j
        if key in self.rc:
            self.cost['intervention_cache_hits']+=1;return self.rc[key]
        self.cost['interventions_executed']+=1
        values=[[] for _ in self.tasks];requests=[]
        for step in range(12):
            if step<len(values):arm=step
            else:
                means=[sum(v)/len(v) for v in values];best=min(means);scores=[]
                for v,m in zip(values,means):
                    var=sum((x-m)**2 for x in v)/max(1,len(v)-1)
                    f=(m,b['scale']*math.sqrt((var+.01)/len(v)),len(v)/12,m-best)
                    scores.append(evaluate(b['ast'],f,'allocator',self.cost))
                arm=min(range(len(values)),key=lambda a:(scores[a],a))
            k=len(values[arm]);v=self.task(arm,j,k%4)[0];values[arm].append(v)
            requests.append([arm,k,v]);self.cost['loss_requests']+=1
        means=[sum(v)/len(v) for v in values]
        arm=min(range(len(values)),key=lambda a:(means[a],size(self.tasks[a]),text(self.tasks[a])))
        tests=[self.task(arm,j,k) for k in (4,5)]
        r={'loss':mean(x[0] for x in tests),'signature':[x[1] for x in tests],
           'task':arm,'requests':requests}
        self.rc[key]=r;return r
    def export(self):
        return [{'bundle':k[0],'block':k[1],**r} for k,r in sorted(self.rc.items())]


def response_key(r):return frozen([r['loss'],r['signature'],r['task'],r['requests']])

def geometry(columns):
    n=len(columns[0]);ids={};groups=[];D=[[Fraction(0) for _ in range(n)] for _ in range(n)]
    for i in range(n):
        sig=tuple(response_key(c[i]) for c in columns);groups.append(ids.setdefault(sig,len(ids)))
        for j in range(n):
            for c in columns:
                a,b=c[i],c[j]
                d=max(abs(Fraction(str(a['loss']))-Fraction(str(b['loss']))),
                    Fraction(frozen(a['signature'])!=frozen(b['signature']),4),
                    Fraction(a['task']!=b['task'],4),Fraction(frozen(a['requests'])!=frozen(b['requests']),4))
                D[i][j]+=d/len(columns)
    return groups,D


def selection(parent,pool,engine,columns):
    groups,D=geometry(columns);D=[[float(x) for x in row] for row in D]
    pilots=[[engine.response(b,j)['loss'] for j in range(3)] for b in pool]
    av=[mean(v) for v in pilots];best=min(av);chosen=[];used=set();ranking=[]
    dev=list(range(3,len(engine.blocks)))
    for _ in range(2):
        eligible=[i for i in range(1,len(pool)) if i not in chosen]
        novel=[i for i in eligible if groups[i] not in used]
        if novel:eligible=novel
        priorities=[]
        for i in eligible:
            variance=mean((x-av[i])**2 for x in pilots[i]);nov=min(D[i][k] for k in [0]+chosen)
            u=math.sqrt((variance+.0001)/3)+.025*nov
            f=(av[i],parent['scale']*u,3/(3+len(dev)),av[i]-best)
            score=evaluate(parent['ast'],f,'allocator',engine.cost)
            priorities.append((score,size(pool[i]['ast']),pool[i]['key'],i,f))
        chosen.append(min(priorities)[3]);used.add(groups[chosen[-1]])
        ranking.append({'eligible':eligible,'chosen':chosen[-1],
                        'priorities':[[p[3],p[0],list(p[4])] for p in priorities]})
    scores=[(mean(engine.response(pool[i],j)['loss'] for j in dev),0 if i==0 else 1,
             size(pool[i]['ast']),pool[i]['key'],i) for i in [0]+chosen]
    winner=min(scores)[-1]
    return pool[winner],{'mode':'space','proposer':parent,'pilot_means':av,'shortlist':chosen,
        'proposal':winner,'scores':[[v[-1],v[0]] for v in scores], 'ranking':ranking,
        'logical_full_checks':len(chosen)*len(dev)}


def verify_ledger(ledger):
    revoked=set();bodies=[]
    for i,r in enumerate(ledger):
        check(r['seq']==i,'ledger sequence')
        for field in ('refs','deps'):
            check(len(set(r[field]))==len(r[field]) and all(type(v)is int and 0<=v<i for v in r[field]),'ledger links')
        b=json.loads(r['body']);bodies.append(b)
        if r['kind']=='revocation':revoked.add(b['root'])
        if r['kind']=='R30_diagnostic_observation':
            intent=bodies[b['intention']]
            paid,H,trace,cost=solve(intent['problem'],b['inferred_mechanism'],intent['program'])
            equal(trace,b['transcript'],'actual observation trace');equal(paid,b['price'])
            check(H==(1<<b['inferred_mechanism']),'inference not grounded')
    invalid=set(revoked)
    for i,r in enumerate(ledger):
        if any(p in invalid for p in r['deps']):invalid.add(i)
    return bodies,invalid


def verify_round(row,banks,seed,phase,index,bodies):
    check(row['phase']==phase and row['index']==index,'round schedule')
    for what in ('task','pool'):
        role='task_pool' if what=='task' else 'candidate_pool'
        check(row[what+'_seed']==innovation(seed,phase,index,role),'innovation mismatch')
    expected_pool=allocator_pool(row['parent'],row['pool_seed'])
    equal(expected_pool,row['pool'],'candidate generator')
    equal(generate_pool(row['old_task'],row['task_seed'],True),row['tasks'],'task generator')
    check(row['new_history_key']==str(innovation(seed,phase,index,'history')),'fresh history')
    check(row['history_keys'][-1]==row['new_history_key'],'history insertion')
    check(row['adoption_keys']==[str(innovation(seed,phase,index,'adoption_'+str(j))) for j in range(4)],'adoption inputs')
    for refs,keys in ((row['history_refs'],row['history_keys']),(row['adoption_refs'],row['adoption_keys'])):
        for ref,key in zip(refs,keys):
            cases=bodies[ref]['cases']
            equal([{'problem':x['problem'],'identified':x['inferred']} for x in cases],banks[key],'grounded bank')
            for case in cases:
                receipt=bodies[case['receipt']];equal(receipt['inferred_mechanism'],case['inferred'])
                check(receipt['intention']==case['intention'],'paired receipt')
    engine=Engine(row['tasks'],[banks[k] for k in row['history_keys']])
    columns=[[engine.response(b,j) for b in row['pool']] for j in range(3)]
    group,distance=geometry(columns)
    equal(group,row['space']['groups'],'classes')
    equal([[str(x) for x in a] for a in distance],row['space']['distance_rationals'],'metric exact')
    cand,selected=selection(row['parent'],row['pool'],engine,columns)
    equal(cand,row['candidate'],'candidate');equal(selected,row['selection'],'selection')
    equal(engine.export(),row['proposal_responses'],'proposal execution')
    equal(dict(engine.cost),row['proposal_cost'],'proposal accounting')
    ae=Engine(row['tasks'],[banks[k] for k in row['adoption_keys']])
    old=[ae.response(row['parent'],j)['loss'] for j in range(4)]
    new=[ae.response(cand,j)['loss'] for j in range(4)]
    accepted=cand['key']!=row['parent']['key'] and mean(old)-mean(new)>.002
    equal(old,row['check']['old']);equal(new,row['check']['new']);check(accepted==row['check']['accepted'],'adoption rule')
    child=cand if accepted else row['parent'];equal(child,row['would_deploy'],'would-deploy')
    equal(ae.export(),row['adoption_responses'],'adoption execution');equal(dict(ae.cost),row['adoption_cost'],'adoption cost')
    check(row['proposal_ref']<min(row['adoption_refs']),'post-selection evidence timing')
    check(row['check']['certificate']['distribution_certificate']=='UNKNOWN','false distribution certificate')
    return ae


def verify_deploy(row,ae,installed,bodies):
    equal(row['bundle'],installed,'installed bundle')
    equal(bodies[row['binding']]['bundle'],installed,'actual binding record')
    response=ae.response(installed,0)
    check(row['task_index']==response['task'],'actual task selected by installed allocator')
    equal(bodies[row['task_ref']]['task_ast'],row['task_ast'],'bound task')
    check(row['step']['executed'] and not row['step']['mismatch'],'base control')


def verify_origin(data):
    check(data['stage']=='R41','stage');seed=data['seed'];banks=data['banks']
    for key,rows in banks.items():equal(bank(int(key)),rows,'external generator/'+key)
    prefix=data['prefix'];pb,_=verify_ledger(prefix)
    last_bundle=bundle(INITIAL['ast'],1.);last_task=0
    for j,row in enumerate(data['root_rounds']):
        equal(row['parent'],last_bundle,'root parent continuity');equal(row['old_task'],last_task,'root task continuity')
        ae=verify_round(row,banks,seed,'root',j,pb)
        if row['check']['accepted']:
            check(j==len(data['root_rounds'])-1 and data['root_present'],'root first acceptance')
        else:
            verify_deploy(row['deployment'],ae,last_bundle,pb)
            last_task=row['deployment']['task_ast']
    if not data['root_present']:
        check(len(data['root_rounds'])==6,'no root search incomplete')
        check(all(x==0 for x in data['metrics'].values()),'no-root convention')
        return {'ok':True,'seed':seed,'root':False,'rounds':6,'banks':len(banks)}
    check(hashed(prefix)==data['prefix_hash'],'prefix hash')
    root=data['root_rounds'][-1];equal(root['parent'],data['root_parent']);equal(root['would_deploy'],data['root_child'])
    check(root['check']['accepted'],'unaccepted root')
    for label,branch in list(data['branches'].items())+[('restore',data['restored']),('annotation',data['annotation_only'])]:
        expected_keep = label.startswith('keep') or label in ('restore','annotation')
        expected_enable = label.endswith('update') or label in ('restore','annotation')
        check(branch['keep']==expected_keep and branch['enable']==expected_enable,'arm assignment')
        bodies,invalid=verify_ledger(prefix+branch['ledger_suffix'])
        equal(sorted(invalid),branch['invalid'],'dependency closure')
        check(branch['prefix_hash']==data['prefix_hash'],'unmatched branch prefix')
        expected=data['root_child'] if branch['keep'] else data['root_parent']
        ae=Engine(root['tasks'],[banks[k] for k in root['adoption_keys']])
        verify_deploy(branch['root_install'],ae,expected,bodies)
        task=branch['root_install']['task_ast'];updates=0;ast_updates=0
        for j,row in enumerate(branch['rounds']):
            equal(row['parent'],expected,'branch parent continuity');equal(row['old_task'],task,'branch task continuity')
            ae=verify_round(row,banks,seed,'future',j,bodies)
            installed=row['would_deploy'] if branch['enable'] else expected
            verify_deploy(row['deployment'],ae,installed,bodies)
            updates+=installed['key']!=expected['key'];ast_updates+=installed['ast']!=expected['ast']
            expected=installed;task=row['deployment']['task_ast']
        equal(expected,branch['endpoint']);check(updates==branch['actual_updates'] and ast_updates==branch['ast_updates'],'update counts')
        check(all(branch['pressure'].values()),'withdrawal reported failure')
        check(branch['rounds'][-1]['deployment']['binding'] in invalid,'current binding not invalid after revoke')
        check(branch['same_instance_within_branch'],'runtime continuity receipt')
    for control in (data['restored'],data['annotation_only']):
        reference=data['branches']['keep_update']
        equal(control['rounds'],reference['rounds'],'replayed full descendant rounds')
        equal(control['endpoint'],reference['endpoint'])
    values={b['endpoint']['key']:[] for b in data['branches'].values()}
    endpoints={b['endpoint']['key']:b['endpoint'] for b in data['branches'].values()}
    for j,row in enumerate(data['audit']['rows']):
        check(row['task_seed']==innovation(seed,'external_audit',j,'task_pool'),'audit task schedule')
        check(row['bank_key']==str(innovation(seed,'external_audit',j,'problem')),'audit bank schedule')
        equal(generate_pool(0,row['task_seed'],True),row['tasks'])
        for k,b in endpoints.items():
            eng=Engine(row['tasks'],[banks[row['bank_key']]])
            r=eng.response(b,0);equal(r,row['responses'][k],'audit response');values[k].append(r['loss'])
    losses={label:mean(values[b['endpoint']['key']]) for label,b in data['branches'].items()}
    equal(losses,data['audit']['losses'])
    g1=losses['keep_frozen']-losses['keep_update'];g0=losses['remove_frozen']-losses['remove_update']
    measures={'benefit_keep':g1,'benefit_remove':g0,'interaction':g1-g0,
              'enabled_total_effect':losses['remove_update']-losses['keep_update'],
              'frozen_root_effect':losses['remove_frozen']-losses['keep_frozen']}
    equal(measures,data['metrics'],'factorial estimands')
    local=min(g1,measures['interaction'],measures['enabled_total_effect'])>1e-12 and data['branches']['keep_update']['actual_updates']>0 and data['branches']['keep_update']['endpoint']['key']!=data['root_child']['key']
    check(local==data['local_productive_causal_candidate'],'local criterion')
    return {'ok':True,'seed':seed,'root':True,'rounds':len(data['root_rounds'])+18,
            'banks':len(banks),'metrics':measures,'local_productive_causal_candidate':local,
            'scope':'independent finite trace reconstruction, not runtime memory identity proof'}
