"""Independent result replay. Imports no Queen, learner or World implementation.
Uses raw public signature tables, ASTs, receipts and frozen source hashes.
Deterministic recurrence/checking arithmetic is duplicated deliberately.
"""
from pathlib import Path
from hashlib import sha256
from collections import defaultdict,deque
from functools import lru_cache
import argparse,json,lzma

ROOT=Path(__file__).resolve().parents[1]
FIELDS=('info','price','spread','order')

def need(x,msg):
    if not x:raise AssertionError(msg)
def normalized(x):
    return tuple(normalized(v) for v in x) if isinstance(x,list) else x

def ev(t,x):
    if type(t)is int:return t*256
    if isinstance(t,str):return x[FIELDS.index(t)]
    a,b=ev(t[1],x),ev(t[2],x)
    op=t[0]
    if op=='+':v=a+b
    elif op=='-':v=a-b
    elif op=='*':v=a*b//256
    elif op=='/':v=a*256//(abs(b)+1)
    else:raise ValueError('unsupported generated opcode')
    return max(-10**9,min(10**9,v))
def nodecount(t):return 1 if isinstance(t,(int,str)) else 1+nodecount(t[1])+nodecount(t[2])
def features(p,H,q):
    n=H.bit_count();counts=[(x&H).bit_count() for x in p['masks'][q]]
    return ((n*n-sum(c*c for c in counts))*1024//(n*n),p['prices'][q]*128,
            sum(c>0 for c in counts)*128,q*16)

def simulation(ast,p,h):
    H=(1<<p['count'])-1;available=list(range(len(p['masks'])));paid=0;steps=[]
    while H.bit_count()>1:
        qs=[q for q in available if features(p,H,q)[0]>0]
        need(qs,'identification failed')
        query=max(qs,key=lambda q:(ev(ast,features(p,H,q)),-q))
        value=next(i for i,m in enumerate(p['masks'][query]) if (m>>h)&1)
        old=H;H &= p['masks'][query][value];paid+=p['prices'][query];available.remove(query)
        steps.append((query,value,old,H))
    return paid,steps

def verify_ledger(records,invalid):
    known=set();children=defaultdict(set)
    for i,r in enumerate(records):
        need(r['seq']==i,'ledger order')
        for j in r['refs']+r['deps']:need(0<=j<i,'forward reference')
        for j in r['deps']:
            need(j not in known,'used invalid support');children[j].add(i)
        data=json.loads(r['body'])
        if r['kind']=='revocation':
            queue=deque([data['root']]);new=set()
            while queue:
                k=queue.popleft()
                if k in known:continue
                known.add(k);new.add(k);queue.extend(children[k])
            need(sorted(new)==data['invalidated'],'retraction closure')
    need(known==set(invalid),'final invalid set')

def reconstruct_monitor(rows,donor=False):
    counts=defaultdict(lambda:[1,2]);total=[1,2]
    for r in rows:
        if donor:
            p,obj,goal,t,action,issued,obs,ok=r;repeats=t['repeats'];margin=t['margin']
        else:
            p,obj,goal,repeats,margin,action,issued,obs,ok,key=r
        observed=obs[0]==obs[1] and obs[0][obj]==goal
        need(observed==ok,'monitor train label not from observations')
        cell=(repeats,sum(margin>x for x in (.20,.55,1.1)))
        counts[cell][0]+=ok;counts[cell][1]+=1;total[0]+=ok;total[1]+=1
    return counts,total

def type2_auc(ps,ys):
    pos=[p for p,y in zip(ps,ys) if y];neg=[p for p,y in zip(ps,ys) if not y]
    return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))

def verify_monitor(e):
    m=e['metacognition'];counts,total=reconstruct_monitor(m['train']);donor,_=reconstruct_monitor(m['donor_training'],True)
    need([[*k,*v] for k,v in sorted(counts.items())]==m['own_model']['cells'],'learned reliability')
    need([[*k,*v] for k,v in sorted(donor.items())]==m['other_model']['cells'],'donor reliability')
    s=e['initial']['initial_self']['options'][0];g=e['initial']['world_gain']
    raw=[]
    for r in m['test']:
        t=r['trace'];key=(t['repeats'],sum(t['margin']>x for x in (.20,.55,1.1)))
        a,n=counts.get(key,[1,2]);other_a,other_n=donor.get(key,[1,2])
        p=r['probabilities']
        need(p['own']==p['restored']==p['renamed']==a/n,'confidence not from learned own counts')
        need(p['blind']==total[0]/total[1] and p['transplant']==other_a/other_n,'confidence ablation')
        order=sorted(range(7),key=lambda a:(r['scores'][a],a))
        need(order[0]==r['fast_action'],'fast action not actual competition winner')
        need(abs(r['scores'][order[1]]-r['scores'][order[0]]-t['margin'])<1e-12,'internal margin')
        raw.append((r['positions'][r['object']]+s*g*r['fast_action'])%7==r['goal'])
    for name,arm in m['arms'].items():
        selected=set(arm['checked']);need(len(selected)==len(arm['checked']),'duplicate checking')
        if name not in ('always_check','never_check'):
            need(len(selected)==32,'unequal quota')
            high=max(m['test'][j]['probabilities'][name] for j in selected)
            low=min(m['test'][j]['probabilities'][name] for j in range(128) if j not in selected)
            need(high<=low,'not checking least reliable items')
        correct=0
        for j,(r,out) in enumerate(zip(m['test'],arm['outputs'])):
            a=r['fast_action']
            if j in selected:a=(r['goal']-r['positions'][r['object']])*pow(s*g,-1,7)%7
            final=(r['positions'][r['object']]+s*g*a)%7;ok=final==r['goal']
            need(out==[a,final,ok],'counterfactual world action');correct+=ok
        need(correct==arm['correct'] and sum(raw)==arm['raw_correct'],'arm scores')
        if name in m['test'][0]['probabilities']:
            probs=[r['probabilities'][name] for r in m['test']]
            brier=sum((p-int(y))**2 for p,y in zip(probs,raw))/len(raw)
            need(abs(brier-arm['brier'])<1e-12,'Brier')
            need(abs(type2_auc(probs,raw)-arm['type2_auc'])<1e-12,'type2 AUC')
    for j,(r,p) in enumerate(zip(m['test'],m['actual_primary'])):
        need(r['forecast']<p[0],'confidence after outcome')
        out=m['arms']['own']['outputs'][j]
        need(p[1]==s*out[0]%7 and p[2][0][r['object']]==out[1] and p[3]==out[2],'actual primary action replay')
    need(all(e['monitor_withdrawal'].values()),'monitor validity lifecycle')
    return len(m['test'])*len(m['arms'])

def verify_phase(phase):
    out=ROOT/'results/r4_r7';summary=json.loads((out/(phase+'_summary.json')).read_bytes())
    data=lzma.decompress((ROOT/summary['archive']).read_bytes());need(sha256(data).hexdigest()==summary['raw_sha256'],'raw hash')
    r=json.loads(data);frozen={'sources':r['sources']} if phase=='dev' else json.loads((out/'FROZEN.json').read_bytes())
    need(r['sources']==frozen['sources'],'frozen source link')
    for p,h in frozen['sources'].items():need(sha256((ROOT/p).read_bytes()).hexdigest()==h,'source changed: '+p)
    catalog=r['problem_catalog']
    for h,p in catalog.items():
        enc=(json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        need(sha256(enc).hexdigest()==h,'problem catalog identity')
    replayed=0;meta=0;mon=0;ledger_n=0
    cohorts={}
    for e in r['rows']:
        cohorts.setdefault(e['seed'],{})[e['method']]=e
        hist=[];old=('/', 'info','price') if e['method']=='hand_query' else 0
        test=[(catalog[c['problem']],c['target_evaluator_only']) for c in e['heldout_cases']]
        total_delta=0;links=[]
        for gen in e['rounds']:
            for c in gen['live']:
                p=catalog[c['problem']];h=c['target_evaluator_only'];obs=c['observed']
                cost,steps=simulation(old,p,h);need(cost==obs['price'],'actual own diagnostic cost')
                got=[tuple(row[k] for k in ('query','value','before','after')) for row in obs['steps']]
                need(got==steps and obs['identified']==h,'actual own posterior not from replies')
                hist.append((p,h));replayed+=len(steps)
            training=hist[-24:];fit=training[::2];check=training[1::2]
            ast=normalized(gen['policy_ast']);evr=gen['evaluation_only']
            scores=[simulation(ast,p,h)[0] for p,h in test]
            need(scores==evr['current_replays'] and sum(scores)==evr['current'],'test result')
            if gen['primary'] is not None:
                pool=[normalized(x) for x in gen['pool']]
                for record,proposer,result_ast in ((gen['primary'],0 if e['method']=='frozen_parent' else old,ast),
                          (evr['counter_search'],0,normalized(evr['counter_ast']))):
                    ds=[]
                    for candidate in pool:
                        vals=[]
                        for p,h in fit[:3]:
                            price,st=simulation(candidate,p,h)
                            vals.append((1024,price*128,1024//len(st),nodecount(candidate)*16))
                        ds.append([sum(v[i] for v in vals)//len(vals) for i in range(4)])
                    need(ds==record['descriptors'],'meta descriptors not actual pilots')
                    order=sorted(range(len(pool)),key=lambda i:(-ev(proposer,ds[i]),i))[:6]
                    need(order==record['selected'],'parent was not used for shortlist')
                    full={i:sum(simulation(pool[i],p,h)[0] for p,h in fit) for i in order}
                    for cost,size,txt,i in record['scores']:need(cost==full[i] and size==nodecount(pool[i]),'candidate evaluation score')
                    oldfit=sum(simulation(old,p,h)[0] for p,h in fit);need(oldfit==record['old_score'],'retention score')
                    best=min(record['scores']);oldcheck=sum(simulation(old,p,h)[0] for p,h in check)
                    newcheck=sum(simulation(pool[best[-1]],p,h)[0] for p,h in check)
                    need(record['adoption_check']==[oldcheck,newcheck],'adoption guard')
                    accept=best[0]<oldfit and newcheck<=oldcheck
                    need(accept==record['accepted'],'acceptance criteria changed')
                    need(result_ast==(pool[best[-1]] if accept else old),'executed successor not selected program')
                    meta+=1
                cf=normalized(evr['counter_ast']);cs=[simulation(cf,p,h)[0] for p,h in test]
                before=sum(simulation(old,p,h)[0] for p,h in test)
                need(cs==evr['counter_replays'] and sum(cs)==evr['frozen_parent'],'matched frozen counterfactual')
                link=gen['generation']>0 and gen['primary']['accepted'] and sum(scores)<before and sum(scores)<sum(cs)
                need(link==evr['strict_link'],'recursive contribution label')
            else:link=False
            links.append(link)
            if gen['generation']>0:total_delta+=evr['delta']
            old=ast
        need(total_delta==e['recursive_delta'] and sum(links)==e['strict_links'],'recursive totals')
        if 'metacognition' in e:mon+=verify_monitor(e)
        if e['ledger'] is not None:verify_ledger(e['ledger'],e['invalid']);ledger_n+=len(e['ledger'])
    for seed,es in cohorts.items():
        need(set(es)=={'recursive','plain','frozen_parent','fixed_query','hand_query'},'missing baseline')
        a,b=es['recursive'],es['plain']
        need(a['rounds']==b['rounds'] and a['metacognition']==b['metacognition'],'plain-log mismatch')
    return {'phase':phase,'status':'VERIFIED','raw_sha256':summary['raw_sha256'],
            'lineages':len(r['rows']),'actual_diagnostic_queries':replayed,'meta_searches_replayed':meta,
            'metacognitive_arm_trials':mon,'ledger_records_replayed':ledger_n}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('A','B','both'));args=ap.parse_args()
    phases=('A','B') if args.phase=='both' else (args.phase,)
    results=[verify_phase(p) for p in phases]
    print(json.dumps(results,ensure_ascii=False,indent=2))
