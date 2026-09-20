"""R37 supplemental exact shortest-distinguishing-word ultrametric.
Runs on the frozen learned quotient AFTER experimental decisions. No feedback.
"""
from collections import deque
from fractions import Fraction
from itertools import product

def sequence_metric(quotient,discount=Fraction(1,2)):
    discount=Fraction(discount)
    if not 0<discount<1:raise ValueError('discount must lie strictly between zero and one')
    states=sorted({s for s,a in quotient});actions=sorted({a for s,a in quotient})
    if set(quotient)!={(s,a) for s in states for a in actions}:raise ValueError('complete quotient required')
    if any(t not in states for o,t in quotient.values()):raise ValueError('next state out of scope')
    words={};D={}
    for first,second in product(states,repeat=2):
        queue=deque([(first,second,())]);seen={(first,second)};word=None
        while queue and word is None:
            s,t,prefix=queue.popleft()
            for a in actions:
                os,ns=quotient[s,a];ot,nt=quotient[t,a]
                if os!=ot:word=prefix+(a,);break
                if (ns,nt) not in seen:seen.add((ns,nt));queue.append((ns,nt,prefix+(a,)))
        words[first,second]=word;D[first,second]=Fraction() if word is None else discount**(len(word)-1)
    for s,t in product(states,repeat=2):
        value=max(max(Fraction(quotient[s,a][0]!=quotient[t,a][0]),discount*D[quotient[s,a][1],quotient[t,a][1]]) for a in actions)
        if value!=D[s,t]:raise RuntimeError('discounted fixed point mismatch')
        if D[s,t]!=D[t,s]:raise RuntimeError('metric symmetry')
        for u in states:
            if D[s,u]>max(D[s,t],D[t,u]):raise RuntimeError('strong triangle inequality')
    return {'discount':str(discount),'states':states,'matrix':[[str(D[s,t]) for t in states] for s in states],
            'max_distinguishing_length':max((len(w) for w in words.values() if w is not None),default=0),
            'is_metric_on_quotient':all(D[s,t]>0 for s,t in product(states,repeat=2) if s!=t),
            'fixed_point_and_ultrametric_checked':True,
            'witnesses':[[s,t,None if w is None else [list(a) if isinstance(a,tuple) else a for a in w]] for (s,t),w in words.items()]}
