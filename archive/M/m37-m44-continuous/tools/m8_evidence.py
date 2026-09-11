"""还原并核验 M8–M11 原记录。纯无损解码，不重新运行实验生成证据。"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from random import Random
import json
import lzma
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from library_m8.core import canonical


def restore(payload):
    report = payload["report_without_noise_rows"]
    report = deepcopy(report)
    # 公共随机码本 + 实测差值的无损表示；不调用模拟器、学习器或实验入口。
    errors = []
    for seed in range(4096):
        rng = Random(seed)
        errors.extend(sum(rng.random() < 0.1 for _ in range(11)) for _ in range(8))
    for index, count in payload["noise_counts_encoding"]["override_counts"]:
        errors[index] = count
    rows = []
    n = report["experiments"]["M10"]["summary"]["repeats"]
    for seed in range(4096):
        truth = seed % 256
        counts = errors[seed * 8: (seed + 1) * 8]
        ones = [n - e if (truth >> x) & 1 else e for x, e in enumerate(counts)]
        error_mask = sum(int(e > n // 2) << x for x, e in enumerate(counts))
        rows.append([seed, truth, ones, error_mask])
    report["experiments"]["M10"]["noise_rows"] = rows
    reports = [(payload["final_sha256"], report)]
    original = deepcopy(report)
    for operation in payload["original_patch"]:
        target = original
        for key in operation["path"][:-1]:
            target = target[key]
        last = operation["path"][-1]
        if operation["op"] == "delete":
            del target[last]
        else:
            target[last] = operation["value"]
    reports.append((payload["original_sha256"], original))
    return reports


def main():
    path = ROOT / "results/m8_m11/evidence_payload.json.xz"
    payload = json.loads(lzma.decompress(path.read_bytes()))
    verified = []
    for expected, report in restore(payload):
        raw = canonical(report)
        actual = sha256(raw).hexdigest()
        if actual != expected:
            raise RuntimeError("decoded evidence hash mismatch")
        output = ROOT / "results/m8_m11/runs" / (expected + ".json.xz")
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            if lzma.decompress(output.read_bytes()) != raw:
                raise RuntimeError("existing raw archive differs")
        else:
            output.write_bytes(lzma.compress(raw, preset=9))
        verified.append(expected)
        if expected == payload["final_sha256"]:
            for name, digest in report["source_sha256"].items():
                if sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                    raise RuntimeError("current source mismatch: " + name)
    print(json.dumps({"verified_original_records": verified,
                      "current_sources_match_final": True}, indent=2))


if __name__ == "__main__":
    main()
