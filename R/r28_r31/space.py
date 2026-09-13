"""R29: finite intervention-response space with revocable witness coordinates.

A response is obtained by actually executing a bounded policy replacement in
an already inferred finite mechanism. This is an interventional simulator,
not identification of arbitrary causal structure from observational logs.
The coordinate construction rule is supplied by the researcher.
"""
from dataclasses import dataclass
from hashlib import sha256
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class Response:
    loss: float
    signature: tuple
    task: int
    requests: tuple

    def json(self):
        return {"loss": self.loss, "signature": self.signature,
                "task": self.task, "requests": self.requests}


def freeze(value):
    return tuple(freeze(x) for x in value) if isinstance(value, (list, tuple)) else value


class CausalSpace:
    """A pseudometric on candidate bundles, a metric on observed equivalence classes.

    Coordinates are retained only when they split a current response class.
    All raw interventions remain in the ledger. Equivalence is local to the
    witnessed protocols; candidates are never permanently deleted.
    """
    def __init__(self, queen, pool, columns, supports):
        if not columns or not pool or len(columns) != len(supports):
            raise ValueError("nonempty matched intervention data required")
        if any(len(col) != len(pool) for col in columns):
            raise ValueError("incomplete response column")
        self.queen = queen
        self.pool = tuple(pool)
        self.axes = []
        self.events = []
        self.groups = [0] * len(pool)
        self.responses = []
        self.splits = []
        signatures = [() for _ in pool]
        for j, column in enumerate(columns):
            old = signatures
            new = [old[i] + (freeze(column[i].signature),) for i in range(len(pool))]
            old_count, new_count = len(set(old)), len(set(new))
            # The first coordinate establishes a nonempty scope, even if constant.
            if j == 0 or new_count > old_count:
                self.axes.append(j)
                signatures = new
                record = queen.add("R29_intervention_coordinate", {
                    "axis": j,
                    "bundle_ids": [b.key for b in pool],
                    "responses": [x.json() for x in column],
                    "classes_before": old_count,
                    "classes_after": new_count,
                    "scope": "executed finite inferred-mechanism intervention only"
                }, deps=(supports[j],))
                self.events.append(record)
                self.responses.append(column)
                if new_count > old_count:
                    self.splits.append([j, old_count, new_count])
        self.version = queen.add("R29_causal_space", {
            "axes": self.axes, "coordinates": self.events,
            "dimension": len(self.axes), "splits": self.splits,
            "kernel": "deterministic observed intervention-response kernels",
            "not_claimed": "global equivalence, intrinsic dimension, causal manifold or consciousness"
        }, deps=tuple(self.events))
        self.groups = self._group(signatures)
        self.signature_rows = signatures

    @staticmethod
    def _group(rows):
        index = {}
        return [index.setdefault(row, len(index)) for row in rows]

    def require(self):
        if self.version in self.queen.ledger.invalid:
            raise PermissionError("causal space evidence withdrawn")

    def distance(self, first, second):
        self.require()
        return sum(a != b for a, b in zip(self.signature_rows[first],
                                         self.signature_rows[second])) / len(self.axes)

    def matrix(self, mode="space"):
        self.require()
        rows = self.signature_rows
        if mode == "graph":
            # Independent reconstruction from typed ledger edges, not cached rows.
            claim = self.queen.read(self.version)
            columns = [self.queen.read(k)["responses"] for k in claim["coordinates"]]
            rows = [tuple(freeze(col[i]["signature"]) for col in columns)
                    for i in range(len(self.pool))]
        elif mode == "shuffled":
            # Wrong intervention-to-bundle association, NOT a harmless axis permutation.
            rows = rows[1:] + rows[:1]
        elif mode == "collapsed":
            rows = [rows[0]] * len(rows)
        groups = self._group(rows)
        distances = [[sum(a != b for a, b in zip(x, y)) / len(self.axes)
                      for y in rows] for x in rows]
        return groups, distances

    def public(self):
        return {"dimension": len(self.axes), "axes": self.axes,
                "classes": len(set(self.groups)), "groups": self.groups,
                "splits": self.splits, "coordinate_records": self.events,
                "space_record": self.version}
