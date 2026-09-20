"""R37 newly authored read-only verifier, NOT the missing original verify.py.
No import of Queen, learners, their partition refinement, or their metric code.
Verifies recorded evidence and arithmetic; not an independent implementation of
all synthetic diagnostic-world generation or of the experimental scheduler.
"""
from collections import deque
from fractions import Fraction
from itertools import product
from pathlib import Path
from statistics import mean
import argparse
import hashlib
import json
import lzma
import math

STATES=tuple(product(range(7),repeat=3))
ACTIONS=tuple(product(range(2),range(7)))
EPS=1e-12

def check(ok,why):
    if not ok: raise ValueError(why)

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def freeze(x):return tuple(map(freeze,x)) if isinstance(x,(list,tuple)) else x
def size(x):return 1 if isinstance(x,(int,str)) else 1+size(x[1])+size(x[2])
def rat(x):return Fraction(str(x))
def close(a,b):return math.isfinite(a) and math.isfinite(b) and abs(a-b)<=EPS

def expression(tree,x):
    if type(tree) is int:return float(tree)
    if isinstance(tree,str):return x[('mean','uncert','visits','gap').index(tree)]
    a,b=expression(tree[1],x),expression(tree[2],x)
    if tree[0]=='+':v=a+b
    elif tree[0]=='-':v=a-b
    elif tree[0]=='*':v=a*b
    elif tree[0]=='/':v=a/(abs(b)+.001)
    else:raise ValueError('allocator expression opcode')
    return max(-1e6,min(1e6,v))

def bundle(b):
    check(b['key']==digest([b['ast'],b['scale']]),'bundle hash')
    check(b['scale'] in (.5,1.,2.),'bundle scale')
    check(size(b['ast'])<=15,'bundle grammar bound')

def decode(packet,offsets):
    check(set(packet)=={'workers'},'observation capability schema')
    rows=[[(v-offsets[j])%7 for v in row] for j,row in enumerate(packet['workers'])]
    check(len(rows)==2 and rows[0]==rows[1] and len(rows[0])==2,'worker agreement')
    return rows[0]

def ledger_check(records):
    bodies=[];bad=set();roots=set()
    for i,r in enumerate(records):
        check(r['seq']==i,'ledger sequential index')
        for key in ('refs','deps'):
            check(len(set(r[key]))==len(r[key]) and all(type(j)is int and 0<=j<i for j in r[key]),'ledger backward links')
        body=json.loads(r['body']);bodies.append(body)
        if r['kind']=='revocation':roots.add(body['root'])
    bad=set(roots)
    for i,r in enumerate(records):
        if any(j in bad for j in r['deps']):bad.add(i)
    return bodies,bad

def pair_partition(transitions,outputs,states=STATES,actions=ACTIONS):
    """Independent greatest-bisimulation test by deleting distinguishable pairs.
    This uses pair reachability, not the learner's state-partition recursion.
    """
    states=tuple(states);idx={s:i for i,s in enumerate(states)}
    check(set(transitions)=={(s,a) for s in states for a in actions},'pair checker complete transitions')
    check(set(outputs)==set(transitions),'pair checker complete outputs')
    def pair(x,y):
        i,j=idx[x],idx[y]
        return (min(i,j),max(i,j))
    signatures={s:tuple(outputs[s,a] for a in actions) for s in states}
    pending={};bad=set()
    for i,s in enumerate(states):
        for j in range(i+1,len(states)):
            t=states[j];p=(i,j)
            if signatures[s]!=signatures[t]:bad.add(p)
            else:pending[p]={pair(transitions[s,a],transitions[t,a]) for a in actions if transitions[s,a]!=transitions[t,a]}
    while True:
        added={p for p,deps in pending.items() if deps & bad}
        if not added:break
        bad.update(added)
        for p in added:del pending[p]
    return bad

def execute_word(first,word,T,O):
    out=[];s=first
    for a in word:
        out.append(O[s,a]);s=T[s,a]
    return tuple(out)

def closure_check(c,bodies,records,fixture=None):
    check(c['states']==343 and c['actions']==14,'closure scope')
    check(len(c['rows'])==4802,'closure coverage count')
    T={};O={}
    for row in c['rows']:
        s,a=tuple(row['state']),tuple(row['action']);key=s,a
        check(key not in T and s in STATES and a in ACTIONS,'closure unique cells')
        i,o=row['intention'],row['observation'];intent,obs=bodies[i],bodies[o]
        check(records[i]['kind']=='intention' and records[o]['kind']=='observation','closure actual record kinds')
        check(obs['intention']==i and i in records[o]['refs'],'closure observation-intention association')
        check(i in row['support'] and o in row['support'],'closure evidence support')
        check(all(0<=ref<c['license'] for ref in row['support']),'closure temporal evidence order')
        before=decode(intent['before'],intent['offsets']);after=decode(obs['after'],intent['offsets'])
        check(tuple(before)+(intent['last'],)==s,'closure prestate from actual observations')
        check((intent['object'],intent['issued'])==a and intent['requested']==a[1],'closure actually issued action')
        target=tuple(after)+(intent['issued'],);effect=tuple((y-x)%7 for x,y in zip(before,after))
        check(target==tuple(row['next']) and effect==tuple(row['output']),'closure effect/transition evidence')
        T[key]=target;O[key]=effect
        if fixture:
            d,k,op,threshold,g=fixture['parameters'];obj,command=a
            p,other,h=s[obj],s[1-obj],s[2]
            gain=(g[3] if (h<threshold if op=='less' else h==threshold) else g[1]) if (p-other)%7==d else (g[2] if obj==k else g[0])
            expected=tuple((gain*command)%7 if j==obj else 0 for j in range(2))
            check(effect==expected,'independent evaluator fixture equation')
    check(set(T)=={(s,a) for s in STATES for a in ACTIONS},'complete transition universe')
    groups={tuple(s):g for s,g in c['groups']}
    check(set(groups)==set(STATES),'complete quotient state map')
    Q={(g,tuple(a)):(tuple(o),t) for g,a,o,t in c['quotient']}
    check(len(Q)==len(set(groups.values()))*14,'complete quotient action map')
    for (s,a),t in T.items():check(Q[groups[s],a]==(O[s,a],groups[t]),'quotient transition congruence')
    bad=pair_partition(T,O)
    for i,s in enumerate(STATES):
        for j in range(i+1,343):check((groups[s]!=groups[STATES[j]])==((i,j) in bad),'maximal/minimal predictive quotient')
    memory=any(len({O[(p0,p1,h),a] for h in range(7)})>1 for p0,p1 in product(range(7),repeat=2) for a in ACTIONS)
    check(memory==c['memory_field_needed'],'memory-omission diagnostic')
    witness=c['long_witness']
    if witness:
        s,t=tuple(witness['first']),tuple(witness['second']);w=tuple(tuple(a) for a in witness['word'])
        check(all(O[s,a]==O[t,a] for a in ACTIONS),'witness is not one-step-distinguished')
        check(execute_word(s,w,T,O)!=execute_word(t,w,T,O),'genuine multistep distinguishing witness')
        check(len(w)<=343,'finite distinguishing bound')
    payload={k:v for k,v in c.items() if k not in ('license','binding','model_hash')}
    check(digest(payload)==c['model_hash'],'closed model payload hash')
    check(bodies[c['license']]==dict(payload,model_hash=c['model_hash']),'model ledger payload binding')
    check(c['license'] in records[c['binding']]['deps'],'model execution-binding dependency')
    for row in c['rows']:check(set(row['support'])<=set(records[c['license']]['deps']),'all transition supports license')
    return {'cells':4802,'classes':len(set(groups.values())),'distinguishable_pairs':len(bad),'memory_required':memory,'long_witness_length':len(witness['word']) if witness else None}

def metric_check(space,bodies,context):
    atom_refs=space['coordinate_records'];atoms=[bodies[j] for j in atom_refs]
    n=len(space['groups']);mass=sum((Fraction(a['weight']) for a in atoms),Fraction())
    check(str(mass)==space['mass'] and mass>0,'metric mass')
    check(all(a['context']==digest(context)==space['context'] for a in atoms),'context-qualified response atoms')
    check(len({a['support'] for a in atoms})==len(atoms),'receipt deduplication')
    ds=[[Fraction() for j in range(n)] for i in range(n)];rs=[Fraction()]*n;matrices=set()
    for atom in atoms:
        col=atom['responses'];w=Fraction(atom['weight']);check(len(col)==n and w>=0,'metric atom domain')
        mat=[]
        for i in range(n):
            rs[i]+=w*rat(col[i]['loss'])/mass
            for j in range(n):
                a,b=col[i],col[j]
                d=max(abs(rat(a['loss'])-rat(b['loss'])),Fraction(a['signature']!=b['signature'],4),Fraction(a['task']!=b['task'],4),Fraction(a['requests']!=b['requests'],4))
                ds[i][j]+=w*d/mass;mat.append(d)
        if w:matrices.add(tuple(mat))
    check([[str(v) for v in row] for row in ds]==space['distance_rationals'],'distance arithmetic')
    check([str(v) for v in rs]==space['risk_rationals'],'risk arithmetic')
    check(len(matrices)==space['compressed_pieces'],'measure-preserving compression piece count')
    for i,j in product(range(n),repeat=2):
        check((ds[i][j]==0)==(space['groups'][i]==space['groups'][j]),'metric-zero quotient')
        check(ds[i][j]==ds[j][i] and abs(rs[i]-rs[j])<=ds[i][j],'symmetry and loss domination')
        for k in range(n):check(ds[i][k]<=ds[i][j]+ds[j][k],'triangle inequality')
    return ds

def finite_certificate(selection,pool,lookup):
    n=selection['full_cap']//len(pool);obs=selection['observed_cells'];lo=[];hi=[]
    check(n>0 and len(obs)==len(pool),'finite certificate scope')
    trace=selection['trace'];check(len(trace)==selection['queries']<=selection['full_cap'],'finite query bound')
    check(len({(i,j) for i,j,v in trace})==len(trace),'finite no replicated evidence')
    recorded={(i,j):str(v) for i,items in enumerate(obs) for j,v in items}
    check({(i,j):str(v) for i,j,v in trace}==recorded,'finite trace cell binding')
    for i,items in enumerate(obs):
        check(len(set(j for j,v in items))==len(items),'unique bank cells')
        values=[]
        for j,v in items:
            v=Fraction(v);check(0<=v<=1,'finite loss bound')
            check(v==rat(lookup[pool[i]['key'],j]['loss']),'finite observed response binding');values.append(v)
        l=sum(values,Fraction())/n;u=l+Fraction(n-len(items),n);lo.append(l);hi.append(u)
    check([str(x) for x in lo]==selection['lower'] and [str(x) for x in hi]==selection['upper'],'finite interval arithmetic')
    b=selection['candidate'];epsilon=Fraction(selection['epsilon'])
    check(all(hi[b]<=lo[i]+epsilon for i in range(len(pool)) if i!=b),'finite-optimum certificate')
    return True

def selection_check(selection,candidate,pool,lookup):
    if 'status' in selection:
        finite_certificate(selection,pool,lookup)
        check(candidate['key']==pool[selection['candidate']]['key'],'finite selected identity');return
    for rank in selection['ranking']:
        rows=rank['priorities'];check(set(p[0] for p in rows)==set(rank['eligible']),'selection eligible coverage')
        for i,score,features in rows:check(close(score,expression(selection['proposer']['ast'],features)),'selection interpreter score')
        picked=min(rows,key=lambda row:(row[1],size(pool[row[0]]['ast']),pool[row[0]]['key'],row[0]))[0]
        check(picked==rank['chosen'],'selection score minimum')
    check([r['chosen'] for r in selection['ranking']]==selection['shortlist'],'selection shortlist')
    scores=selection['scores'];check({i for i,l in scores}=={0,*selection['shortlist']},'selection checked shortlist scope')
    nblocks=1+max(j for key,j in lookup);pilot=min(3,nblocks-1);dev=range(pilot,nblocks)
    for i,l in scores:check(close(l,mean(lookup[pool[i]['key'],j]['loss'] for j in dev)),'selection development score')
    b=min(scores,key=lambda row:(row[1],0 if row[0]==0 else 1,size(pool[row[0]]['ast']),pool[row[0]]['key']))[0]
    check(b==selection['proposal'] and candidate['key']==pool[b]['key'],'proposal minimum and identity')

def verify_episode(r):
    records=r['ledger'];bodies,bad=ledger_check(records)
    check(sorted(bad)==r['invalid'],'independent invalidity propagation')
    c=closure_check(r['closure'],bodies,records,r['fixture_evaluator_only'])
    check(len(r['rounds'])==6,'trajectory six generations')
    updates=regressions=strict=certificates=0;losses=[]
    for g,row in enumerate(r['rounds']):
        check(row['generation']==g,'generation order')
        bundle(row['parent']);bundle(row['child']);updates+=row['adopted']
        check(row['adopted']==(row['parent']['key']!=row['child']['key']),'actual bundle update flag')
        if g:check(row['parent']['key']==r['rounds'][g-1]['child']['key'],'persistent allocator continuity')
        prop=bodies[row['proposal_record']];ck=bodies[row['check_record']]
        check(ck['proposal']==row['proposal_record'] and ck['child']==row['child'],'proposal adoption link')
        check(row['proposal_record']<row['check_record']<row['task_binding'],'temporal proposal/adoption/binding order')
        for dep in records[row['check_record']]['deps']:
            if dep!=row['proposal_record']:check(dep>row['proposal_record'],'new adoption evidence after frozen proposal')
        check(prop['context']['inner_budget']==12 and len(prop['pool'])==8 and len(prop['tasks'])==6,'fixed experimental budgets')
        lookup={(x['bundle'],x['block']):x for x in row['proposal_interventions']}
        adop={(x['bundle'],x['block']):x for x in row['adoption_interventions']}
        for b in prop['pool']:bundle(b)
        for name,br in prop['branches'].items():
            bundle(br['candidate']);selection_check(br['selection'],br['candidate'],prop['pool'],lookup)
            check(row['branches'][name]==br['candidate']['key'],'branch proposal identity')
            a=row['checks'][name]
            expected_old=[adop[row['parent']['key'],j]['loss'] for j in range(4)]
            expected_new=[adop[br['candidate']['key'],j]['loss'] for j in range(4)]
            check(a['old']==expected_old and a['new']==expected_new,'adoption response evidence')
            accepted=br['candidate']['key']!=row['parent']['key'] and mean(a['old'])-mean(a['new'])>.002
            check(a['accepted']==accepted,'adoption rule')
            check(a['certificate']['distribution_certificate']=='UNKNOWN','no invented distribution certificate')
        primary=prop['branches']['primary']['candidate'] if row['checks']['primary']['accepted'] else row['parent']
        check(primary['key']==row['child']['key'],'deployment matches accepted full bundle')
        if r['method']!='legacy':
            metric_check(row['space'],bodies,prop['context'])
            check(all(v['metric_equal'] and v['same_candidate'] for v in row['invariance']),'measured evidence-order invariance')
        eval_=row['evaluation_only'];means={k:mean(v) for k,v in eval_['blocks'].items()}
        check(all(len(v)==6 and all(0<=x<=1 for x in v) for v in eval_['blocks'].values()),'evaluation loss scope')
        check(all(close(means[k],v) for k,v in eval_['means'].items()),'evaluation mean arithmetic')
        d=means['parent']-means['child'];gp=means['previous']-means['child'];gi=means['initial']-means['child']
        check(close(d,row['delta']) and close(gp,row['gamma_previous']) and close(gi,row['gamma_initial']),'causal gain arithmetic')
        flag=g>0 and row['previous_adopted'] and row['adopted'] and min(d,gp,gi)>EPS
        check(flag==row['strict_empirical_link'],'strict recursion definition');strict+=flag;regressions+=d < -EPS;losses.append(means['child'])
        if row['finite_certificate'] is not None:finite_certificate(row['finite_certificate'],prop['pool'],lookup);certificates+=1
        move=row['spatial_step'];intent=bodies[move['intention']];obs=bodies[move['observation']]
        after=decode(obs['after'],intent['offsets'])
        check(obs['intention']==move['intention'] and after==move['predicted'],'actual control predicted effect')
        check(after[move['object']]==move['goal'] and intent['issued']==move['action'],'actual control goal')
    summary=r['summary']
    for k,value in {'updates':updates,'regressions':regressions,'strict_links':strict,'finite_exact_certificates':certificates,'quotient_classes':c['classes'],'closure_cells':4802}.items():check(summary[k]==value,'summary '+k)
    check(close(summary['test_loss'],mean(losses)),'test loss summary')
    p=r['pressure'];check(p['allocator_root'] in bad and p['controller_root'] in bad,'revoked roots persisted')
    check(r['closure']['license'] in bad and r['closure']['binding'] in bad,'old control authorization invalid')
    check(p['new_controller']['model'] not in bad and p['new_controller']['binding'] not in bad,'new controller evidence valid')
    check(p['recovery_new_cells']==1 and p['recovery_cost']['R34_closure_probe_moves']==1,'one actual cell recovery')
    check(p['recovery_control']['correct'] and p['recovery_control']['executed'],'restored actual control')
    check(summary['all_controls_correct'] and summary['all_pressure_pass'],'runtime control guard checks')
    seq=r['sequence_evaluation_only']
    if r['method']=='measured' and seq.get('status') is None:
        check(seq['words']==67228 and seq['transitions']==134456 and seq['passed'] and not seq['failures'],'length-two execution bank')
    return {'seed':r['seed'],'method':r['method'],'valid':True,'ledger_records':len(records),'closure':c,'verified_rounds':6,'finite_certificates':certificates,
            'scope':'independent evidence/partition/metric/selection arithmetic checks; original evaluator generator not independently reimplemented'}

def verify_file(path):
    path=Path(path);data=path.read_bytes();raw=lzma.decompress(data);r=json.loads(raw)
    result=verify_episode(r);result.update(file=path.name,raw_sha256=hashlib.sha256(raw).hexdigest(),xz_sha256=hashlib.sha256(data).hexdigest())
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('paths',nargs='+');a=p.parse_args()
    for name in a.paths:print(json.dumps(verify_file(name),ensure_ascii=False),flush=True)
