"""R37 supplemental overlap guard; never substituted into the frozen A/B learner.
A transition map is only defined on shared positive-mass protocol evidence.
"""
from fractions import Fraction
from r32_r37.space import rho,response_key

def checked_overlap(a,b):
    a.require();b.require()
    if a.queen is not b.queen:
        raise ValueError('different ledger namespaces: no receipt identity transport supplied')
    if a.context!=b.context or a.metric!=b.metric:
        return {'status':'CONVENTION_MISMATCH','comparable':False}
    points=sorted({p.key for p in a.pool}&{p.key for p in b.pool})
    aa={s:(c,w) for s,c,w in a.atoms};bb={s:(c,w) for s,c,w in b.atoms}
    atoms=sorted(set(aa)&set(bb));ai={p.key:i for i,p in enumerate(a.pool)};bi={p.key:i for i,p in enumerate(b.pool)}
    for atom in atoms:
        ca,wa=aa[atom];cb,wb=bb[atom]
        if wa!=wb:raise ValueError('same atom has different mass')
        if any(response_key(ca[ai[p]])!=response_key(cb[bi[p]]) for p in points):
            raise ValueError('same point and atom has a different response')
    mass=sum((aa[s][1] for s in atoms),Fraction())
    if not points or mass<=0:return {'status':'NO_POSITIVE_OVERLAP','comparable':False}
    def matrix(bank,index):
        return [[sum((bank[s][1]*rho(bank[s][0][index[p]],bank[s][0][index[q]],a.metric) for s in atoms),Fraction())/mass for q in points] for p in points]
    left,right=matrix(aa,ai),matrix(bb,bi)
    if left!=right:raise RuntimeError('common-protocol transport not isometric')
    return {'status':'EXACT_ON_COMMON_MEASURE','comparable':True,'points':points,'atoms':atoms,
            'mass':str(mass),'distance_rationals':[[str(v) for v in row] for row in left],
            'not_claimed':'isometry of full unequal evidence banks or a global manifold'}
