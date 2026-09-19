"""R33/R34: measure-preserving, revocable finite intervention-response spaces.
Researcher-supplied mathematics and implementation. No networking or autonomous code generation.
"""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import isfinite
from r28_r31.space import freeze, canonical, digest


def rational(value):
    if isinstance(value, Fraction):
        return value
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError('finite numeric value required')
    return Fraction(str(value))


def response_key(response):
    return freeze((response.loss, response.signature, response.task, response.requests))


def rho(a, b, metric='measured'):
    if metric == 'hamming':
        return Fraction(response_key(a) != response_key(b))
    if metric != 'measured':
        raise ValueError('unknown metric')
    # Maximum of component pseudometrics. It dominates absolute realized loss difference.
    return max(abs(rational(a.loss) - rational(b.loss)),
               Fraction(1, 4) * (freeze(a.signature) != freeze(b.signature)),
               Fraction(1, 4) * (a.task != b.task),
               Fraction(1, 4) * (freeze(a.requests) != freeze(b.requests)))


class MeasuredSpace:
    """Finite local chart. A receipt is an atom; re-reading it does not add mass.
    Distinct atoms with identical distance matrices can be compressed by ADDING mass.
    An additional real intervention changes the target measure, even if constant.
    """
    def __init__(self, queen, pool, columns, supports, context, metric='measured', weights=None):
        if not pool or not columns or len(columns) != len(supports):
            raise ValueError('nonempty complete paired evidence required')
        if len({b.key for b in pool}) != len(pool):
            raise ValueError('duplicate point identities')
        self.queen, self.pool, self.context, self.metric = queen, tuple(pool), digest(context), metric
        weights = [1] * len(columns) if weights is None else list(weights)
        if len(weights) != len(columns):
            raise ValueError('weight count mismatch')
        atoms = {}
        for column, support, weight in zip(columns, supports, weights):
            if len(column) != len(pool):
                raise ValueError('incomplete response column')
            if type(support) is not int or not 0 <= support < len(queen.ledger.records):
                raise ValueError('unknown support')
            queen.read(support)  # Refuse withdrawn evidence before constructing anything.
            weight = rational(weight)
            if weight < 0:
                raise ValueError('negative measure')
            for r in column:
                if not 0 <= rational(r.loss) <= 1:
                    raise ValueError('loss outside declared range')
            identity = (self.context, support)
            descriptor = (tuple(response_key(r) for r in column), weight)
            if identity in atoms:
                if atoms[identity][2] != descriptor:
                    raise ValueError('same receipt given inconsistent response or weight')
                continue
            atoms[identity] = (tuple(column), weight, descriptor)
        self.atoms = tuple((key[1], *atoms[key][:2]) for key in sorted(atoms))
        self.mass = sum((w for _, _, w in self.atoms), Fraction())
        if self.mass <= 0:
            raise ValueError('positive total protocol mass required')
        self.signature_rows = [tuple(response_key(col[i]) for _, col, w in self.atoms if w > 0)
                               for i in range(len(pool))]
        self.groups = self._group(self.signature_rows)
        self.axes = [support for support, _, w in self.atoms if w > 0]
        self.events = []
        self.distance_ops = 0
        for support, column, weight in self.atoms:
            record = queen.add('R34_response_atom', {
                'context': self.context, 'point_ids': [b.key for b in pool],
                'support': support, 'weight': str(weight),
                'responses': [r.json() for r in column]
            }, deps=(support,))
            self.events.append(record)
        self.version = queen.add('R34_measured_space', {
            'context': self.context, 'metric': metric, 'atoms': self.events,
            'point_ids': [b.key for b in pool], 'mass': str(self.mass),
            'scope': 'observed finite protocol only; no global program equivalence'
        }, deps=tuple(self.events))
        self._distances = self._compute(self.atoms)
        # Exact metric compression by equal per-atom dissimilarity matrices.
        pieces = {}
        for support, col, weight in self.atoms:
            if not weight:
                continue
            matrix = tuple(rho(a, b, metric) for a in col for b in col)
            pieces[matrix] = pieces.get(matrix, Fraction()) + weight
        self.compressed_pieces = tuple(pieces.items())
        n = len(pool)
        self.compressed = [[sum((w * matrix[i*n+j] for matrix, w in self.compressed_pieces),
                               Fraction()) / self.mass for j in range(n)] for i in range(n)]
        if self.compressed != self._distances:
            raise RuntimeError('measure-preserving compression failed')

    @staticmethod
    def _group(rows):
        groups = {}
        return [groups.setdefault(row, len(groups)) for row in rows]

    def require(self, context=None):
        if self.version in self.queen.ledger.invalid:
            raise PermissionError('space support withdrawn')
        if context is not None and digest(context) != self.context:
            raise PermissionError('different intervention protocol; a new chart is required')

    def _compute(self, atoms):
        n = len(self.pool)
        self.distance_ops += n*n*len(atoms)
        return [[sum((w*rho(col[i], col[j], self.metric) for _, col, w in atoms), Fraction())
                 / self.mass for j in range(n)] for i in range(n)]

    def distance(self, first, second):
        self.require()
        return self._distances[first][second]

    def matrix(self, mode='space'):
        self.require()
        groups, distances = list(self.groups), self._distances
        if mode == 'graph':
            from r28_r31.space import Response
            claim = self.queen.read(self.version)
            atoms = []
            for ref in claim['atoms']:
                row = self.queen.read(ref)
                col = tuple(Response(x['loss'], freeze(x['signature']), x['task'], freeze(x['requests']))
                            for x in row['responses'])
                atoms.append((row['support'], col, Fraction(row['weight'])))
            distances = self._compute(atoms)
            rows = [tuple(response_key(col[i]) for _, col, w in atoms if w > 0)
                    for i in range(len(self.pool))]
            groups = self._group(rows)
        elif mode == 'shuffled':
            indices = list(range(1, len(self.pool))) + [0]
            distances = [[distances[i][j] for j in indices] for i in indices]
            groups = [groups[i] for i in indices]
        elif mode == 'collapsed':
            groups = [0]*len(self.pool)
            distances = [[Fraction()]*len(self.pool) for _ in self.pool]
        elif mode != 'space':
            raise ValueError('unknown view')
        return groups, [[float(x) for x in row] for row in distances]

    def risks(self):
        self.require()
        return [sum((w*rational(col[i].loss) for _, col, w in self.atoms), Fraction())/self.mass
                for i in range(len(self.pool))]

    def public(self):
        return {'context': self.context, 'metric': self.metric, 'dimension': len(self.axes),
                'classes': len(set(self.groups)), 'groups': self.groups,
                'mass': str(self.mass), 'compressed_pieces': len(self.compressed_pieces),
                'space_record': self.version, 'coordinate_records': self.events,
                'distance_ops': self.distance_ops,
                'distance_rationals': [[str(x) for x in row] for row in self._distances],
                'risk_rationals': [str(x) for x in self.risks()],
                'risk_bound_checked': all(abs(a-b) <= self.distance(i,j)
                                          for i,a in enumerate(self.risks())
                                          for j,b in enumerate(self.risks()))}


class Atlas:
    """History of context-qualified charts, not an invented global manifold."""
    def __init__(self, queen):
        self.queen, self.charts = queen, []

    def append(self, chart):
        if chart.queen is not self.queen:
            raise ValueError('another ledger owner')
        chart.require()
        self.charts.append(chart)
        return chart.version

    def overlap(self, first, second):
        a,b = self.charts[first], self.charts[second]
        a.require(); b.require()
        if a.context != b.context:
            return {'status':'CONTEXT_MISMATCH', 'comparable':False}
        common_points = sorted({p.key for p in a.pool} & {p.key for p in b.pool})
        common_atoms = sorted({s for s,_,_ in a.atoms} & {s for s,_,_ in b.atoms})
        ai={p.key:i for i,p in enumerate(a.pool)}; bi={p.key:i for i,p in enumerate(b.pool)}
        ac={s:col for s,col,_ in a.atoms}; bc={s:col for s,col,_ in b.atoms}
        aw={s:w for s,_,w in a.atoms}; bw={s:w for s,_,w in b.atoms}
        if any(aw[s] != bw[s] for s in common_atoms):
            raise ValueError('same protocol atom changed measure; new context required')
        agrees=all(response_key(ac[s][ai[p]]) == response_key(bc[s][bi[p]])
                   for s in common_atoms for p in common_points)
        if not agrees:
            raise ValueError('same protocol/receipt/point changed response')
        return {'status':'OVERLAP_ONLY', 'comparable':True,
                'points':len(common_points), 'atoms':len(common_atoms), 'agrees':agrees}


def finite_best(pool, engine, indices, proposer, epsilon=0):
    """Certified epsilon-optimum on THIS FULL DECLARED finite bank, not future data.
    No unknown response is inferred from pilot equivalence. Queries are counted.
    Proposer influences scheduling only; exact risk/tie rules govern the answer.
    """
    from r20_r23_recovery import racing
    indices = tuple(indices)
    if not indices or not pool:
        raise ValueError('empty search scope')
    if len(set(indices)) != len(indices) or len({b.key for b in pool}) != len(pool):
        raise ValueError('duplicate protocol cells or candidate identities')
    epsilon = rational(epsilon)
    if epsilon < 0:
        raise ValueError('negative epsilon')
    n,k=len(indices),len(pool)
    known=[{} for _ in pool]
    costs_before=dict(engine.cost)
    tie=lambda i: (0 if i==0 else 1, racing.size(pool[i].ast), pool[i].key)
    calls=0; trace=[]
    while True:
        lower=[sum(x.values(),Fraction())/n for x in known]
        upper=[lo+Fraction(n-len(x),n) for lo,x in zip(lower,known)]
        best=min(range(k),key=lambda i:(upper[i],tie(i)))
        contenders=[i for i in range(k) if i!=best and
                    (lower[i] < upper[best]-epsilon or
                     (epsilon==0 and lower[i]==upper[best] and tie(i)<tie(best)))]
        if not contenders:
            return pool[best], {'scope':'DECLARED_FINITE_BANK_ONLY', 'status':'EXACT' if epsilon==0 else 'EPSILON',
                'candidate':best, 'lower':[str(x) for x in lower], 'upper':[str(x) for x in upper],
                'epsilon':str(epsilon), 'queries':calls, 'full_cap':k*n,
                'observed_cells':[[[j,str(v)] for j,v in sorted(x.items())] for x in known],
                'trace':trace, 'cost_before':costs_before, 'cost_after':dict(engine.cost)}
        eligible=[i for i in [best]+contenders if len(known[i])<n]
        if not eligible:
            raise RuntimeError('finite-bound search did not terminate')
        def schedule(i):
            mean=float(sum(known[i].values(),Fraction())/len(known[i])) if known[i] else 0.
            f=(mean, float(upper[i]-lower[i])*proposer.scale, len(known[i])/n,
               mean-min(float(x) for x in lower))
            return (racing.Program(proposer.ast)(f,engine.cost),tie(i))
        i=min(eligible,key=schedule)
        j=next(x for x in indices if x not in known[i])
        value=rational(engine.run(pool[i],j).loss)
        if not 0<=value<=1:
            raise ValueError('loss bound invalid')
        known[i][j]=value;calls+=1
        trace.append([i,j,str(value)])
        if calls>k*n:
            raise RuntimeError('declared budget exceeded')
