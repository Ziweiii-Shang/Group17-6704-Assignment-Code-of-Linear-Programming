"""Check raw workbook hashes and their validated cache metadata."""
import hashlib
import pickle
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "processed"
README = RAW / "README.md"

records = re.findall(r"`(instance_[^`]+\.xlsx)`\s*\|\s*`([0-9a-f]{64})`", README.read_text())
if len(records) != 9:
    raise SystemExit(f"Expected 9 workbook hash records in {README}, found {len(records)}")

errors = []
for name, expected_hash in records:
    workbook = RAW / name
    cache = CACHE / f"{Path(name).stem}.input.pkl"
    if not workbook.is_file():
        errors.append(f"Missing workbook: {workbook.relative_to(ROOT)}")
        continue
    actual_hash = hashlib.sha256(workbook.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        errors.append(f"Workbook hash mismatch: {workbook.relative_to(ROOT)}")
    if not cache.is_file():
        errors.append(f"Missing input cache: {cache.relative_to(ROOT)}")
        continue
    with cache.open("rb") as stream:
        data = pickle.load(stream)
    if data.get("source_sha256") != actual_hash:
        errors.append(f"Cache source hash mismatch: {cache.relative_to(ROOT)}")

if errors:
    raise SystemExit("Input verification failed:\n- " + "\n- ".join(errors))
print(f"Verified {len(records)} workbook/cache pairs.")
