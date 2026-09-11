"""不调用学习器：校验原档、源码、反例真实性、累计约束和展开执行结果。"""
from hashlib import sha256
from pathlib import Path
import json,lzma,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from library_m21.synthesis import evaluate,tuple_tree,compile_program,canonical,nodes,expand


def require(value,why):
    if not value:raise AssertionError(why)


def verify(root=ROOT):
    summary=json.loads((root/'results/m21_m24/summary.json').read_text())
    raw=lzma.decompress((root/summary['archive']).read_bytes())
    require(sha256(raw).hexdigest()==summary['result_sha256'],'raw digest')
    result=json.loads(raw)
    for path,value in result['source_sha256'].items():require(sha256((root/path).read_bytes()).hexdigest()==value,path)
    require(result['tests_run']==len(result['test_cases']),'test count')
    require(not result['test_failures'] and not result['test_errors'],'tests failed')
    macros={k:tuple_tree(v) for k,v in result['frozen_learning_state']['macros'].items()}
    rows=list(result['course']['rows'])
    for group in result['transfer']['rows'].values():rows.extend(group)
    rows.extend(result['supplement_large_seed']['rows'])
    for key in ('spike17_with_guard','spike17_without_guard','latent71','wrong_reference'):
        rows.append(result['boundary'][key])
    task_runs=len(rows)
    cex_count=0;replayed=0;all_known_ok=True
    for row in rows:
        known={};rounds=row['rounds']
        meta=row.get('evaluation_only_task')
        def expected(x):
            z=x if 'offset' in meta else meta['a']*x+meta['b']
            f=(z*z, z*(z-1)//2, z*abs(z))[meta['family']]
            return f+meta.get('offset',meta.get('d',0))
        if meta is not None:
            require([expected(x) for x in row['future_inputs']]==row['future_expected'],'independent expected outputs')
        for entry in rounds:
            if 'lowered' not in entry:continue
            expr=tuple_tree(entry['lowered']);ev=dict(entry['evidence'])
            require(expand(tuple_tree(entry['expression']),macros)==expr,'macro unfolding differs')
            if meta is not None:require(all(expected(x)==y for x,y in ev.items()),'false teaching evidence')
            require(all(ev.get(x)==y for x,y in known.items()),'lost previous counterexample')
            require(all(evaluate(expr,x)==y for x,y in entry['evidence']),'historical regression')
            if entry['counterexample'] is not None:
                x,y=entry['counterexample'];require(evaluate(expr,x)!=y,'fake counterexample')
                if meta is not None:require(expected(x)==y,'incorrect oracle counterexample')
                require(entry['old_prediction']==evaluate(expr,x),'wrong old output')
                known[x]=y;cex_count+=1
        require(row['refutations']==sum(e.get('status')=='refuted' for e in rounds),'refutation count')
        if row['accepted']:
            expr=tuple_tree(row['lowered']);fn=compile_program(expr,{})
            require(fn.source==row['source'],'compiled source mismatch')
            require(row['certificate']['program']==fn.fingerprint,'certificate program')
            require(rounds[-1]['checker_visits']==49,'incomplete adopting checker')
            require(row['certificate']['scope']=='finite_checked_domain_only','overbroad certificate')
            values=[evaluate(expr,x) for x in row['future_inputs']]
            require(values==row['future_actual'],'future replay')
            require([fn(x) for x in row['future_inputs']]==values,'compiler/interpreter mismatch')
            correct=sum(x==y for x,y in zip(values,row['future_expected']))
            require(correct==row['future_correct'],'future score')
            require(all(evaluate(expr,x)==y for x,y in row['evidence']),'deployed evidence mismatch')
            require(not set(row['future_inputs'])&set(row['certificate']['domain']),'challenge leaked by domain')
            require(all(evaluate(expr,x)==y for x,y in known.items()),'deployed forgotten refutation')
            replayed+=len(values)
        else:
            require(row['future_actual'] is None,'rejected program counted as deployed')
    require(len(result['course']['rows'])==12,'course coverage')
    require(all(len(rows)==24 for rows in result['transfer']['rows'].values()),'transfer coverage')
    require(result['transfer']['rows']['learned']==result['transfer']['rows']['plain_json'],'same information differs')
    require(len(result['supplement_large_seed']['rows'])==24,'supplement coverage')
    freeze=(canonical(result['frozen_learning_state'])).encode()
    require(sha256(freeze).hexdigest()==result['frozen_learning_state_sha256'],'learning state mismatch')
    return {'verified':True,'result_sha256':summary['result_sha256'],'source_files':len(result['source_sha256']),
            'task_runs_checked':task_runs,
            'actual_refutations_checked':cex_count,'future_outputs_replayed':replayed,
            'note':'回读所有原档与独立树执行；不是重新运行学习实验或独立外部复现。'}

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
