"""M8–M11 独立复现入口，只写 Library/results/m8_m11。"""
from pathlib import Path
from hashlib import sha256
import json
import lzma
import platform
import sys
import traceback
import unittest
from library_m8.core import canonical
from library_m8.study import run_all

ROOT = Path(__file__).resolve().parent
CONTRACT_SHA256 = "a42a84d96e4ae61bb7548c7d28a2c8869c97ae2c99c49cfeea4649403894c7f7"
CONTRACT_COMMIT = "a66442eb217fcc194f5d8e3f221d0d551d808ab7"


class Recorded(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.checks = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.checks.append([test.id(), "PASS"])

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.checks.append([test.id(), "FAIL"])

    def addError(self, test, err):
        super().addError(test, err)
        self.checks.append([test.id(), "ERROR"])


def main():
    files = sorted((ROOT / "library_m8").glob("*.py")) + [ROOT / "run_m8_m11.py",
                                                               ROOT / "docs/M8_M11_CONTRACT.md"]
    manifest = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files}
    tests = Recorded()
    unittest.defaultTestLoader.loadTestsFromName("library_m8.tests").run(tests)
    data, experiment_error = {}, None
    try:
        data = run_all()
    except Exception:
        experiment_error = traceback.format_exc()
    contract_ok = manifest["docs/M8_M11_CONTRACT.md"] == CONTRACT_SHA256
    ok = contract_ok and tests.testsRun > 0 and tests.wasSuccessful() and not tests.skipped and experiment_error is None
    report = {"schema": "library.m8-m11.v1", "research_date": "2026-09-10",
        "contract_commit": CONTRACT_COMMIT, "contract_hash_matches": contract_ok, "python": platform.python_version(),
        "implementation": platform.python_implementation(), "passed": ok,
        "command": "python3 run_m8_m11.py", "tests_run": tests.testsRun,
        "test_cases": tests.checks,
        "failures": [[test.id(), tb] for test, tb in tests.failures],
        "errors": [[test.id(), tb] for test, tb in tests.errors],
        "skipped": [[test.id(), reason] for test, reason in tests.skipped],
        "experiment_error": experiment_error, "source_sha256": manifest, "experiments": data}
    raw = canonical(report)
    digest = sha256(raw).hexdigest()
    destination = ROOT / "results/m8_m11"
    archive = destination / "runs" / (digest + ".json.xz")
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists():
        if lzma.decompress(archive.read_bytes()) != raw:
            raise RuntimeError("archive hash collision or changed data")
    else:
        archive.write_bytes(lzma.compress(raw, preset=9))
    summary = {k: v for k, v in report.items() if k != "experiments"}
    summary.update(result_sha256=digest, archive=str(archive.relative_to(ROOT)),
                   summaries={key: value["summary"] for key, value in data.items()})
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2,
                                                        sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": ok, "tests": tests.testsRun, "python": report["python"],
                     "result_sha256": digest, "summaries": summary["summaries"]},
                    ensure_ascii=False, indent=2, sort_keys=True))
    if experiment_error:
        print(experiment_error, file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
