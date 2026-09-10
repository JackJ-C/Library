"""还原 Git 中的四个证据分片；仅标准库，不执行包内任何代码。"""
import base64
from hashlib import sha256
import json
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = "b8cc833b46e28123eb2395c8b98fcd7b2edfb1a057d76dc0eb1d2576dfd9d823"


def main():
    parts = ROOT / "results" / "evidence_parts"
    text = "".join((parts / f"part{i:02d}.b64").read_text().strip() for i in range(4))
    compressed = base64.b64decode(text, validate=True)
    if sha256(compressed).hexdigest() != EXPECTED:
        raise ValueError("evidence bundle checksum mismatch")
    data = lzma.decompress(compressed)
    bundle = json.loads(data)
    target = ROOT / "results" / "m1_m6_evidence.json"
    if target.exists() and target.read_bytes() != data:
        raise ValueError("refusing to overwrite different evidence")
    if not target.exists():
        target.write_bytes(data)
    print("Evidence verified:", EXPECTED)
    print("Final experiment:", bundle["final_run_sha256"])
    print("Saved:", target)


if __name__ == "__main__":
    main()
