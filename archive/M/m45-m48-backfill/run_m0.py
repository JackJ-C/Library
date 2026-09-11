"""在本仓库复现 M0。仅标准库；失败也保存记录并返回非零状态。"""
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
import traceback
import unittest
from library_m0.witnesses import run_witnesses

ROOT = Path(__file__).resolve().parent
CONTRACT_SHA256 = "226b10ae0b6ae208d9528516990730e76fedc56c90dbb07d4bbfac0c779124d3"
CONTRACT_COMMIT = "65f22aeae2a12f250e522359259f6ca6b3656024"


class RecordedResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.executed = []
        self.checks = []

    def startTest(self, test):
        super().startTest(test)
        self.executed.append(test.id())

    def addSuccess(self, test):
        super().addSuccess(test)
        self.checks.append({"case": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.checks.append({"case": test.id(), "status": "FAIL"})

    def addError(self, test, err):
        super().addError(test, err)
        self.checks.append({"case": test.id(), "status": "ERROR"})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.checks.append({"case": subtest.id(), "status": "FAIL"})


def main():
    tested = sorted(list((ROOT / "library_m0").glob("*.py"))
                    + list((ROOT / "tests").glob("*.py"))
                    + [ROOT / "run_m0.py"]
                    + [ROOT / "docs" / name for name in
                       ("M0_CONTRACT.md", "M0_SPEC.md", "RELATED_WORK.md")])
    manifest = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in tested}
    contract_ok = manifest["docs/M0_CONTRACT.md"] == CONTRACT_SHA256
    result = RecordedResult()
    unittest.defaultTestLoader.loadTestsFromName("tests.test_m0").run(result)
    witness_error = None
    try:
        witnesses = run_witnesses()
    except Exception:
        witnesses, witness_error = {}, traceback.format_exc()
    ok = (contract_ok and result.testsRun > 0 and result.wasSuccessful()
          and not result.skipped and not result.expectedFailures and witness_error is None)
    report = {
        "milestone": "M0", "status": "PASS" if ok else "FAIL",
        "scope": "formal_contract_and_finite_witnesses_not_learning",
        "research_date": "2026-09-10", "contract_commit": CONTRACT_COMMIT,
        "contract_hash_matches": contract_ok,
        "command": "python3 run_m0.py", "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "tests_run": result.testsRun, "checks": result.checks,
        "executed_cases": result.executed,
        "failures": [{"case": t.id(), "traceback": tb} for t, tb in result.failures],
        "errors": [{"case": t.id(), "traceback": tb} for t, tb in result.errors],
        "skipped": [{"case": t.id(), "reason": r} for t, r in result.skipped],
        "witnesses": witnesses, "witness_error": witness_error,
        "source_sha256": manifest
    }
    data = (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    digest = sha256(data).hexdigest()
    output = ROOT / "results"
    archive = output / "runs"
    archive.mkdir(parents=True, exist_ok=True)
    immutable = archive / (digest + ".json")
    if immutable.exists() and immutable.read_bytes() != data:
        raise RuntimeError("run archive collision")
    if not immutable.exists():
        immutable.write_bytes(data)
    # 这是便于阅读的最新结果副本；原记录在内容寻址的 runs/ 中保留。
    (output / "m0_result.json").write_bytes(data)
    print("M0:", report["status"], "| unit cases:", result.testsRun,
          "| witness groups:", len(witnesses), "| Python:", platform.python_version())
    print("Result SHA256:", digest)
    print("Archive:", immutable.relative_to(ROOT))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
