"""Read-only independent archive audit. Does not import or run Queen/the learning loop."""
from collections import Counter, defaultdict, deque
from hashlib import sha256
from pathlib import Path
import argparse
import json
import lzma

ROOT=Path(__file__).resolve().parents[1]
METHODS={'library','plain','recent','masked','no_revision','recalibrate'}


def require(ok, why):
    if not ok:
        raise AssertionError(why)


def verify(phase):
    summary=json.loads((ROOT/f'results/m33_m36/phase_{phase}_summary.json').read_text())
    raw=lzma.decompress((ROOT/summary['archive']).read_bytes())
    require(sha256(raw).hexdigest()==summary['raw_sha256'],'raw archive sha256')
    report=json.loads(raw)
    for path, value in report['frozen_source_sha256'].items():
        require(sha256((ROOT/path).read_bytes()).hexdigest()==value,'source '+path)
    seeds=range(3000,3032) if phase=='C' else range(4000,4032)
    require({(r['seed'],r['method']) for r in report['rows']}=={(s,m) for s in seeds for m in METHODS},'full paired coverage')
    counts=Counter(); trajectories={}
    for row in report['rows']:
        trace=row['trace']; ledger=trace['ledger']; bodies=[json.loads(r['body']) for r in ledger]
        require(trace['instance_preserved'],'persistent object assertion')
        invalid=set(); children=defaultdict(set); cert=None;cert_version=None
        for i,r in enumerate(ledger):
            require(r['seq']==i,'record ordering')
            for parent in r['refs']+r['deps']:
                require(type(parent) is int and 0<=parent<i,'future or nonexistent reference')
            for parent in r['deps']:
                require(parent not in invalid,'new proof dependent on invalid claim')
                children[parent].add(i)
            if r['kind']=='revocation':
                queue=deque([bodies[i]['root']]); changed=set()
                while queue:
                    at=queue.popleft()
                    if at in invalid:
                        continue
                    invalid.add(at);changed.add(at);queue.extend(children[at])
                require(sorted(changed)==bodies[i]['invalidated'],'revocation closure')
            if r['kind']=='certificate':
                cert=i;cert_version=bodies[i]['self_model']['version']
            if r['kind']=='intention':
                require(cert is not None and cert not in invalid,'task intent after invalid permission')
                require(bodies[i]['version']==cert_version,'task version not licensed')
            if r['kind']=='experience':
                f=bodies[i];j=f['intention_slice'];p=bodies[j]
                require(j<i and ledger[j]['kind']=='intention','prediction not committed before outcome')
                require(all(p[k]==f[k] for k in ('prediction','action','before','object','goal','version','delta','inverse')),'intention overwritten')
                for view in f['before']+f['after']:
                    a,b=view['positions']
                    require(view['relations']=={'same_place':a==b,'apple_to_cup_clockwise':(b-a)%7},'worker relation')
                counts['experience_slices']+=1
            if r['kind']=='cross_slice_reinspection':
                b=bodies[i]
                if b['self_intention_inspected']:
                    require(b['intention_slice'] in r['deps'],'missing intention proof dependency')
                counts['reinspections']+=1
        require(invalid==set(trace['invalid']),'invalid-set mismatch')
        require(len(trace['steps'])==72,'trajectory task length')
        for step in trace['steps']:
            if not step['acted']:
                continue
            f=bodies[step['slice']];s,b0,b1,g=step['truth_before'];o=f['object']
            require(f['action']==s*f['delta']*f['inverse']%7,'actual judgement replay')
            observed=f['before'][o]['positions'][o]
            require(f['delta']==(f['goal']-observed)%7,'judgement input replay')
            require((f['after'][0]['positions'][o]-f['before'][0]['positions'][o])%7==g*f['action']%7,'physical action replay')
            require(f['success']==((f['after'][0]['positions'][o]-b0)%7==f['goal']),'success feedback replay')
            counts['online_actions_replayed']+=1
        future_correct=regressions=diagnoses=0
        for audit in trace['audits']:
            r=audit['review'];old=audit['truth_before'];new=audit['truth_after']
            expected={'self':old[0]!=1,'worker0':old[1]!=0,'worker1':old[2]!=0,
                      'environment':old[3]!=r['old_model']['gain']}
            require(expected==audit['expected_diagnosis'],'diagnostic gold mismatch')
            diagnoses+=r['diagnosis']==expected
            c=r['cost'];require(c['reads']<=8 and c['bytes']<=65536 and c['probes']<=8 and c['ops']<=100000,'budget')
            if r['status'] in ('adopted','confirmed'):
                needed={('control_model' if key=='environment' else key) for key,val in expected.items() if val}
                require(set(r['applied_changes'])==needed,'wrong physical component revision')
                require(audit['actual_binding_replaced']==expected['self'],'judge binding mismatch')
            for f in audit['future']:
                o=f['object'];p=f['positions'][o];goal=f['goal']
                a=new[0]*(goal-(p+new[1+o])%7)*pow(r['self_model']['gain'],-1,7)%7
                success=(p+new[3]*a)%7==goal
                require(a==f['action'] and success==f['success'],'future actual-path replay')
                aold=old[0]*(goal-(p+old[1+o])%7)*pow(r['old_model']['gain'],-1,7)%7
                sold=(p+old[3]*aold)%7==goal
                require(aold==f['old_action'] and sold==f['old_success'],'old program counterfactual replay')
                future_correct+=success;regressions+=sold and not success;counts['future_outputs_replayed']+=1
        require(future_correct==row['counts'].get('future_correct',0),'future aggregate')
        require(regressions==row['counts'].get('future_regressions',0),'regression aggregate')
        require(diagnoses==row['counts']['correct_diagnoses'],'diagnosis aggregate')
        for a in trace['attribution']:
            packet=a['public_packet'];answer=a['answer'];observations=packet['observations']
            require(set(packet)=={'observations'},'identity labels in public view')
            require(all(set(r)=={'local_effect','paths'} for r in observations),'identity metadata in row')
            inspected=answer['read_slices']
            require(len(inspected)==len(set(inspected)) and len(inspected)<=8,'identity read budget')
            compatible=[c for c in range(2) if all(row['method']=='masked' or observations[i]['paths'][c]==observations[i]['local_effect'] for i in inspected)]
            probs=[1/len(compatible) if c in compatible else 0 for c in range(2)] if compatible else [None,None]
            require(answer['candidates']==compatible and answer['probability']==probs,'identity answer not based on evidence')
            truth=a['truth_hidden_from_queen']
            require(all(r['paths'][truth]==r['local_effect'] for r in observations),'true historical completion mismatch')
            symmetric=all(r['paths'][0]==r['paths'][1] for r in observations)
            require(symmetric==a['ambiguous_full_view'],'symmetry classification mismatch')
            if symmetric:
                require(answer['probability']==[0.5,0.5],'unjustified certain origin')
            counts['attributions_replayed']+=1
        trajectories[(row['seed'],row['method'])]=row
        counts['trajectories_verified']+=1
    for seed in seeds:
        a,b=trajectories[(seed,'library')],trajectories[(seed,'plain')]
        require(a['counts']==b['counts'] and a['trace']==b['trace'],'same-information baseline mismatch')
    p=report['pressure']
    for kind in ('misleading_reference','nonlinear_sensor'):
        require(p[kind]['status']=='rolled_back' and p[kind]['restored'] and p[kind]['blocked'] and not p[kind]['permit'],'rollback stress')
    require(p['revocation']['execution_denied'] and p['revocation']['review_survives'],'revocation stress')
    require(p['latent_motor']['future_action_failed'] and not p['latent_motor']['post_review_valid'],'latent failure hidden')
    require(p['lying_causal_port']['incorrectly_certain'],'invalid-assumption counterexample hidden')
    return {'phase':phase,'status':'VERIFIED','raw_sha256':summary['raw_sha256'],**counts}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['C','D','both'],default='both')
    args=parser.parse_args()
    result=[verify(p) for p in ('CD' if args.phase=='both' else args.phase)]
    print(json.dumps(result,indent=2))
