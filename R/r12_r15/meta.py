"""Attempt to couple second-order evaluation reliability to the R5 successor loop.
The actual parent still orders successors. A learned, history-based acceptance margin
is tested against fixed-parent and unguarded controls. This is an attempt, not a proof
of RSI. Representation, mutation and margins are researcher-designed.
"""
import json
from dataclasses import asdict
from collections import deque
from r4_r7 import search
from r4_r7.study import own_diagnosis as previous_diagnosis, p_json, test_program

ROUNDS=8
CANDIDATES=24
FULL=4
HAND=('/','info','price')


class EvaluationMonitor:
    """Forecast optimism of the Queen's own fit-based improvement proposals.
    The label is a later, disjoint historical replay, not an evaluator test-set result.
    """
    def __init__(self):
        self.errors=deque(maxlen=16); self.support=[]; self.fixed=None
    def margin(self, q=None, c=None):
        if self.fixed is not None:return self.fixed
        if q is not None and any(k in q.ledger.invalid for k in self.support[-16:]):
            raise PermissionError('withdrawn meta-evaluation evidence')
        if q is None:return sum(self.errors)/len(self.errors) if self.errors else 0
        errors=[]
        for k in self.support[-16:]:
            row=json.loads(q.ledger.records[k].body)
            oldfit,newfit=row['fit_totals'];oldcheck,newcheck=row['check_totals']
            errors.append(abs((oldfit-newfit)/max(1,oldfit)-(oldcheck-newcheck)/max(1,oldcheck)))
            if c:c.feature_ops+=2
        return sum(errors)/len(errors) if errors else 0
    def observe(self,fit_gain,check_gain,key):
        self.errors.append(abs(fit_gain-check_gain));self.support.append(key)


def guarded_successor(q,incumbent,proposer,pool_,history,c,monitor,guard=True):
    fit=history[::2];check=history[1::2]
    descriptors=[search.first_features(a,fit,c) for a in pool_]
    order=sorted(range(len(pool_)),key=lambda i:(-proposer(descriptors[i],c),i))[:FULL]
    old_fit=search.trial_score(incumbent,fit,c)
    scored=[(search.trial_score(pool_[i],fit,c),search.nodes(pool_[i]),search.text(pool_[i]),i) for i in order]
    best=min(scored)
    old_check=search.trial_score(incumbent,check,c)
    new_check=search.trial_score(pool_[best[-1]],check,c)
    gfit=(old_fit-best[0])/max(1,old_fit)
    gcheck=(old_check-new_check)/max(1,old_check)
    margin=monitor.margin(q,c)*.5 if guard else 0
    accepted=best[0]<old_fit and new_check<=old_check and gcheck>=margin
    record={'selected':order,'descriptors':descriptors,'scores':scored,'old_fit':old_fit,
            'old_check':old_check,'new_check':new_check,'fit_gain':gfit,'check_gain':gcheck,
            'predicted_error_margin':margin,'accepted':accepted,
            'parent':proposer.source,'before':incumbent,
            'after':pool_[best[-1]] if accepted else incumbent,'best':best[-1]}
    return record['after'],record


def lineage(q,world,seed,method='coupled',keep_ledger=False):
    """Continues the same Queen after the online experiment, without resetting its memory.
    Performance readouts are not fed into proposal, monitor or acceptance updates.
    """
    qid,lid=id(q),id(q.ledger)
    q.search_program=search.Program(0)
    q.search_license=q.add('R14_search_scope',{'bootstrap':'fixed initial program'})
    q.meta_reliability=EvaluationMonitor()
    monitor=q.meta_reliability
    c=search.Cost();history=[];historical_refs=[];rounds=[]
    cases=[search.make_problem(seed*100000+80000+i,n=(24,40,48)[i%3],nq=(18,30)[i%2]) for i in range(24)]
    for generation in range(ROUNDS):
        live=[]
        for j in range(8):
            p,true=search.make_problem(seed*100000+generation*100+j)
            if q.search_license in q.ledger.invalid: raise PermissionError('withdrawn search program')
            inferred,record=previous_diagnosis(q,p,search.Body(p,true),c)
            support=tuple(k for pair in record['receipts'] for k in pair)
            record['record']=q.add('R14_identified_execution',{'inferred':inferred,'price':record['price']},
                                  refs=(record['record'],),deps=support)
            historical_refs.append(record['record'])
            history.append((p,inferred))
            live.append({'problem':p_json(p),'gold_evaluator_only':true,'observed':record})
        data=history[-32:];parent=q.search_program
        pool_=search.pool(parent.ast,seed*1237+generation,CANDIDATES)
        proposer=search.Program(0) if method=='frozen_parent' else parent
        guarded=method not in ('unguarded','fixed_margin')
        if method=='fixed_margin':
            # Independent, stated strong baseline: no experiential confidence needed.
            monitor.fixed=.10
            guarded=True
        new,primary=guarded_successor(q,parent.ast,proposer,pool_,data,c,monitor,guarded)
        cc=search.Cost()
        counter,cr=guarded_successor(q,parent.ast,search.Program(0),pool_,data,cc,monitor,guarded)
        uc=search.Cost()
        unguarded,ur=guarded_successor(q,parent.ast,proposer,pool_,data,uc,monitor,False)
        # Forecast provenance and observed check-gain are recorded before the monitor updates.
        f=q.add('R14_meta_forecast',{'generation':generation,'margin':primary['predicted_error_margin'],
                'fit_gain':primary['fit_gain'],'old_program':parent.source},
                refs=tuple(monitor.support[-16:]),deps=tuple(monitor.support[-16:]))
        o=q.add('R14_meta_check',{'check_gain':primary['check_gain'],
                 'fit_gain':primary['fit_gain'],'generation':generation,
                 'fit_totals':[primary['old_fit'],min(primary['scores'])[0]],
                 'check_totals':[primary['old_check'],primary['new_check']]},refs=(f,),deps=tuple(historical_refs[-32:]))
        if primary['accepted']:
            q.search_program=search.Program(new)
        update=q.add('R14_meta_revision',primary,refs=(f,o),deps=(q.search_license,f,o))
        if primary['accepted']:q.search_license=update
        monitor.observe(primary['fit_gain'],primary['check_gain'],o)
        bc,br,_=test_program(parent.ast,cases)
        nc,nr,_=test_program(q.search_program.ast,cases)
        fc,fr,_=test_program(counter,cases)
        ucst,ureplay,_=test_program(unguarded,cases)
        strict=(generation>0 and primary['accepted'] and nc<bc and nc<fc)
        rounds.append({'generation':generation,'live':live,'pool':pool_,'primary':primary,
            'frozen_counter':cr,'unguarded_counter':ur,'before_cost':bc,'current_cost':nc,
            'frozen_cost':fc,'unguarded_cost':ucst,'strict_link':strict,
            'regression':nc>bc,'counter_cost':asdict(cc),'unguarded_search_cost':asdict(uc),
            'actual_rebind':q.search_program is not parent,'record':update,
            'current_replay':nr,'counter_replay':fr,'unguarded_replay':ureplay})
    flags=[r['strict_link'] for r in rounds]
    result={'seed':seed,'method':method,'rounds':rounds,'cost':asdict(c),
            'heldout':[{'problem':p_json(p),'gold_evaluator_only':h} for p,h in cases],
            'accepted':sum(r['actual_rebind'] for r in rounds),
            'strict_links':sum(flags),'consecutive':any(a and b for a,b in zip(flags,flags[1:])),
            'regressions':sum(r['regression'] for r in rounds),
            'final_cost':rounds[-1]['current_cost'],
            'paired_gain':sum(r['frozen_cost']-r['current_cost'] for r in rounds[1:])/(7*len(cases)),
            'hand_baseline_cost':test_program(HAND,cases)[0],
            'initial_baseline_cost':test_program(0,cases)[0],
            'same_queen':id(q)==qid,'same_ledger':id(q.ledger)==lid,
            'ledger':q.ledger.export() if keep_ledger else None,
            'invalid':sorted(q.ledger.invalid)}
    return result
