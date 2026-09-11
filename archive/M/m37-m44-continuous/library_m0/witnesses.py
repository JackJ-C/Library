"""有限穷举和手工切片链；所有答案由构造得出，不是自主发现。"""
from collections import defaultdict
from dataclasses import asdict
from itertools import product
from .core import Actor, ContractError, Library, square


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def run_witnesses():
    gaps = []
    for old, new, target in product((0, 1), repeat=3):
        gaps.append({"old": old, "new": new, "target": target,
                     "gap": abs(old - new),
                     "utility": abs(old - target) - abs(new - target)})
    changed = [r for r in gaps if r["gap"] == 1]
    improved = sum(r["utility"] > 0 for r in changed)
    worsened = sum(r["utility"] < 0 for r in changed)
    check(improved == 2 and worsened == 2, "gap direction counterexample")

    groups = defaultdict(list)
    for history in product((0, 1), repeat=4):
        groups[sum(history)].append({"history": history,
                                    "failure_positions": [i for i, v in enumerate(history) if v == 0]})
    ambiguous = sum(len(rows) > 1 for rows in groups.values())
    check(len(groups) == 5 and ambiguous == 3, "summary information collision")

    observed_groups = defaultdict(list)
    squares = []
    for table in product((0, 1), repeat=4):
        # 顺序是 (00,01,10,11)；观测仅有 00 和 11。
        observed_groups[str((table[0], table[3]))].append(table)
        decomposition = square(*table)
        check(decomposition["total"] == sum(decomposition[k]
              for k in ("reader", "evidence", "interaction")), "square identity")
        squares.append({"cells": table, **decomposition})
    check(all(len(rows) == 4 for rows in observed_groups.values()), "diagonal ambiguity")
    self_world, environment_world = (0, 0, 1, 1), (0, 1, 0, 1)
    check((self_world[0], self_world[3]) == (environment_world[0], environment_world[3]),
          "observed worlds must match")
    check(self_world[1] != environment_world[1], "controlled probe must separate these two worlds")

    library = Library()
    worker, q0, q1 = Actor("worker", "v0"), Actor("queen", "v0"), Actor("queen", "v1")
    records = [library.append("action", worker, 1, 1, {"action": "left", "outcome": None})]
    records.append(library.append("feedback", worker, 1, 3, {"outcome": 0}, refs=("action",)))
    records.append(library.append("review-0", q0, 4, 4,
                                 {"alternatives": ["worker", "environment"]},
                                 "review", ("action", "feedback")))
    records.append(library.append("review-1", q1, 5, 5,
                                 {"missing_probe": "hold environment fixed"},
                                 "review", ("review-0",)))
    future_blocked = False
    try:
        library.read("feedback", 1, q1)
    except ContractError:
        future_blocked = True
    full = library.traverse("review-1", 5, q1)
    bounded = library.traverse("review-1", 5, q1, max_nodes=2)
    check(future_blocked and len(full.keys) == 4 and not full.truncated and bounded.truncated,
          "walkthrough contract")
    return {
        "W1_gap_not_progress": {"status": "PASS", "cases": gaps,
                               "changed": 4, "improved": improved, "worsened": worsened},
        "W2_summary_collision": {"status": "PASS", "histories": 16, "summary_classes": 5,
                                 "ambiguous_classes": ambiguous, "groups_by_sum": dict(groups)},
        "W3_attribution_ambiguity": {"status": "PASS", "tables": 16,
                                     "observation_classes": dict(observed_groups),
                                     "self_world": self_world, "environment_world": environment_world,
                                     "probe": {"version": 0, "environment": 1,
                                               "self_world_y": 0, "environment_world_y": 1}},
        "W4_square_identity": {"status": "PASS", "tables": 16, "cases": squares,
                               "nonzero_interactions": sum(r["interaction"] != 0 for r in squares)},
        "W5_manual_walkthrough": {"status": "PASS", "autonomous": False,
                                  "future_blocked": future_blocked,
                                  "records": [asdict(r) for r in records],
                                  "full": asdict(full), "bounded": asdict(bounded)}
    }
