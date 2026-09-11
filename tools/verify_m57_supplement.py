"""M57 supplemental audit: frozen verifier retained, table predictions replay stored table source. No learner or raw-data changes."""
from pathlib import Path
from hashlib import sha256
from collections import Counter,defaultdict,deque
import argparse,json,lzma
ROOT=Path(__file__).resolve().parents[1]

def need(x,msg):
    if not x:raise AssertionError(msg)

def term(e,s):
    op=e[0]
    if op=='field':return s[e[1]]
    if op=='constant':return e[1]
    a,b=term(e[1],s),term(e[2],s)
    return (a-b)%7 if op=='difference' else (a==b if op=='equals' else a<b)

def tree(t,s):
    return t[1] if t[0]=='gain' else tree(t[2] if term(t[1],s) else t[3],s)

def physics(params,level,s):
    d,obj,op,t,g=params;p,o,j,h=s
    if level==0:return g[0]
    if (p-o)%7==d:return g[3] if level>=3 and (h<t if op=='less' else h==t) else g[1]
    return g[2] if level>=2 and j==obj else g[0]

def verify(phase):
    meta=json.loads((ROOT/f'results/m54_m57/{phase}.json').read_bytes())
    data=lzma.decompress((ROOT/meta['archive']).read_bytes());need(sha256(data).hexdigest()==meta['raw_sha256'],'raw checksum')
    run=json.loads(data);frozen=json.loads((ROOT/'results/m54_m57/freeze.json').read_bytes())
    for p,h in frozen['sources'].items():need(sha256((ROOT/p).read_bytes()).hexdigest()==h,'source mismatch '+p)
    need(run['source_sha256']==frozen['sources'],'manifest mismatch')
    need({(r['seed'],r['method']) for r in run['rows']}=={(s,m) for s in frozen[phase] for m in ('library','plain','fixed','table','no_history','no_structure')},'paired coverage')
    totals=Counter()
    for r in run['rows']:
        ledger=r['ledger'];bodies=[json.loads(x['body']) for x in ledger];invalid=set();children=defaultdict(list); active_function=False
        table_versions={v['version']:{tuple(k):val for k,val in json.loads(v['source'])} for v in r['revisions']+r['extra_revisions'] if r['method']=='table'}
        for i,z in enumerate(ledger):
            if z['kind']=='task_permission':active_function=True
            elif z['kind']=='unresolved':active_function=False
            need(z['seq']==i,'nonsequential records')
            for k in z['refs']+z['deps']:need(0<=k<i,'future edge')
            for k in z['deps']:need(k not in invalid,'invalid support reused');children[k].append(i)
            if z['kind']=='revocation':
                body=bodies[i];q=deque([body['root']]);changed=set()
                while q:
                    k=q.popleft()
                    if k in invalid:continue
                    invalid.add(k);changed.add(k);q.extend(children[k])
                need(sorted(changed)==body['invalidated'],'proof closure mismatch')
            if z['kind']=='observation':
                o=bodies[i];j=o['intention'];a=bodies[j];need(j<i and ledger[j]['kind']=='intention','late intention')
                need(set(o['after'])=={'workers'},'gold feedback leak')
                need('correct' not in a and 'success' not in a,'gold label in intention')
                if a['model'] is not None:
                    gain=(table_versions.get(a['version'],{}).get(tuple(a['state'])) if r['method']=='table' else tree(a['model'],a['state'])) if active_function else None
                    delta=None if gain is None else gain*a['issued']%7
                    expected=None if delta is None else [(a['before']['workers'][0][k]-a['offsets'][0]+(delta if k==a['object'] else 0))%7 for k in (0,1)]
                    need(a['predicted_after']==expected,'prediction recomputation')
                totals['observed_actions']+=1
        need(invalid==set(r['invalid']),'invalid final state')
        # Every actual mover event is replayed by independent arithmetic.
        for e in r['physics']:
            gain=physics(r['parameters_gold'],e['level_gold'],e['state']);obj=e['state'][2]
            need(e['gain_gold']==gain,'hidden simulator law disagrees with independent arithmetic')
            need(e['after'][obj]==(e['before'][obj]+gain*e['command'])%7,'movement mismatch')
            need(e['after'][1-obj]==e['before'][1-obj],'cross effect')
            totals['physical_moves']+=1
        correct=0;regressions=0
        for stage in r['stages']:
            for z in stage['future']:
                need(z['state'][0] in (1,3,5),'not held out')
                if r['method']=='table':
                    need(all(tuple(z['state']) not in tab for tab in table_versions.values()),'table contains holdout')
                    need(z['intended_command'] is None and z['command'] is None,'unseen table state executed')
                gain=physics(r['parameters_gold'],stage['level_gold'],z['state']);a=z['command']
                ok=a is not None and (z['state'][0]+gain*a)%7==z['goal']
                need(ok==z['correct'],'future score');correct+=ok
                regressions+=z['old_rule_still_applicable'] and not ok;totals['future_cases']+=1
        need(correct==r['counts']['future_correct'] and regressions==r['counts']['regressions'],'aggregate score')
        for z in r['attribution']:
            packet=z['packet'];need(set(packet)=={'paths'},'identity schema')
            need(all(set(p)=={'before','after'} for p in packet['paths']),'identity metadata')
            a=z['answer'];truth=z['truth_gold']
            if z['symmetric']:need(packet['paths'][0]==packet['paths'][1] and a['probabilities']==[.5,.5],'symmetric certainty')
            else:need(a['options']==[truth],'distinct attribution')
            need(z['permutation_ok'],'permutation');totals['attributions']+=1
        for rec in ledger:
            if rec['kind']=='model_revision':
                b=json.loads(rec['body']);col=b['same_command_conflicting_effects']
                if col:
                    i,j=col['first'][0],col['second'][0];need(bodies[i]['issued']==bodies[j]['issued']==col['same_command'],'false same-command witness')
                    need(col['gains'][0]!=col['gains'][1],'not a counterexample');totals['same_command_witnesses']+=1
        totals['records']+=len(ledger);totals['trajectories']+=1
    return {'phase':phase,'status':'VERIFIED','raw_sha256':meta['raw_sha256'],'counts':dict(totals),'scope':'independent arithmetic/data replay, not independent research team or full formal verification'}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=('A','B','both'),nargs='?',default='both');a=ap.parse_args()
    out=[verify(p) for p in ('AB' if a.phase=='both' else a.phase)]
    (ROOT/'results/m54_m57/supplemental_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False))
