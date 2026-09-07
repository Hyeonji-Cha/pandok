import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/Hyeonji-Cha/pandok/main/contracts/telemetry-event-v2.schema.json"
EXPECTED_GIT_BLOB_SHA = "4336417ea4107e4e9597ecddbcf989f38a240f7f"
DEST = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("telemetry-event-v2.schema.json")

with urllib.request.urlopen(URL, timeout=20) as response:
    data = response.read()

blob_sha = hashlib.sha1(
    f"blob {len(data)}\0".encode("ascii") + data
).hexdigest()
if blob_sha != EXPECTED_GIT_BLOB_SHA:
    raise SystemExit(
        f"Refusing contract: expected Git blob {EXPECTED_GIT_BLOB_SHA}, got {blob_sha}"
    )

parsed = json.loads(data.decode("utf-8"))
if parsed.get("$id") != "https://pandok.dev/contracts/telemetry-event-v2.schema.json":
    raise SystemExit("Refusing contract: unexpected $id")
if parsed.get("$defs", {}).get("commonBase", {}).get("properties", {}).get("schema_version") != {"const": "2.0"}:
    raise SystemExit("Refusing contract: schema_version is not exactly 2.0")

DEST.parent.mkdir(parents=True, exist_ok=True)
fd, tmp_name = tempfile.mkstemp(prefix=DEST.name + ".", dir=str(DEST.parent))
try:
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_name, DEST)
finally:
    if os.path.exists(tmp_name):
        os.unlink(tmp_name)

print(f"OK: wrote exact canonical contract to {DEST}")
print(f"Git blob SHA: {blob_sha}")
