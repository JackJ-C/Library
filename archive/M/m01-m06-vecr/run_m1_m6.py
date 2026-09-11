"""M1–M6：仅本仓库写结果；不联网、不训练、不使用 GitHub Actions。"""
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import platform
import sys
import time
import traceback
import unittest
from library_m1plus.checks import Checks
from library_m1plus.study import run_study

ROOT = Path(__file__).resolve().parent
CONTRACT_COMMIT = "5bb97212419515f7bf2e3c0a9df0fbb2b35f75e3"


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def table(rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def main():
    start = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    sources = sorted((ROOT / "library_m1plus").glob("*.py")) + [ROOT / "run_m1_m6.py"]
    manifest = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in sources}
    summary, cases, random_rows, transitions, example = {}, [], [], [], None
    failure = None
    try:
        summary, cases, random_rows, transitions, example = run_study()
    except Exception:
        failure = traceback.format_exc()
    ok = tests.wasSuccessful() and not tests.skipped and failure is None
    report = dict(status="PASS" if ok else "FAIL", contract_commit=CONTRACT_COMMIT,
                  python=platform.python_version(), tests=tests.testsRun,
                  failures=len(tests.failures), errors=len(tests.errors), skipped=len(tests.skipped),
                  source_sha256=manifest, results=summary, study_error=failure)
    raw = {}
    if cases:
        raw = {"worlds.csv": table(cases), "transitions.csv": table(transitions),
               "random.csv": table([dict(world=h, seed=s, queries=q) for h, s, q in random_rows]),
               "example_trace.json": encoded(example)}
    report["raw_sha256"] = {name: sha256(data).hexdigest() for name, data in raw.items()}
    data = encoded(report)
    digest = sha256(data).hexdigest()
    out = ROOT / "results" / "m1_m6" / digest
    out.mkdir(parents=True, exist_ok=True)
    artifacts = {"summary.json": data, "test_log.txt": stream.getvalue().encode()}
    artifacts.update(raw)
    # 每轮用 summary 内容摘要定址；原始数据改变时拒绝覆盖。
    for name, contents in artifacts.items():
        target = out / name
        if target.exists() and target.read_bytes() != contents:
            if name != "test_log.txt":
                raise RuntimeError("immutable run collision: " + name)
        elif not target.exists():
            target.write_bytes(contents)
    (ROOT / "results" / "m1_m6_latest.json").write_bytes(data)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("RESULT_SHA256", digest)
    print("ELAPSED_SECONDS", round(time.monotonic() - start, 3))
    print("ARCHIVE", out)
    if failure:
        print(failure)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
