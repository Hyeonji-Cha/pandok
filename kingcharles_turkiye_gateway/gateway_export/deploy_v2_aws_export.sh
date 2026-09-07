#!/usr/bin/env bash
set -euo pipefail

STAGE_DIR="${1:-$(pwd)}"
APP_DIR="/opt/pandok-gateway"
VENV="$APP_DIR/venv"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
CONTRACT="$STAGE_DIR/telemetry-event-v2.schema.json"
EXPORT_CONF="/etc/pandok-gateway/export.conf"
DROPIN_DIR="/etc/systemd/system/pandok-gateway.service.d"
DROPIN="$DROPIN_DIR/20-aws-export.conf"

cd "$STAGE_DIR"

if [[ ! -f "$EXPORT_CONF" ]]; then
  echo "ERROR: $EXPORT_CONF is missing. Create it from pandok-gateway-export.conf.example on the server." >&2
  exit 1
fi
if ! grep -Eq '^PANDOK_AWS_EXPORT_ENABLED=1$' "$EXPORT_CONF"; then
  echo "ERROR: PANDOK_AWS_EXPORT_ENABLED=1 is not configured." >&2
  exit 1
fi
if grep -Eq 'REDACTED|AWS_INGEST_ENDPOINT|<AWS' "$EXPORT_CONF"; then
  echo "ERROR: export.conf still contains a placeholder endpoint." >&2
  exit 1
fi
TOKEN_PATH="$(awk -F= '$1=="PANDOK_AWS_EXPORT_TOKEN_PATH" {print substr($0,index($0,"=")+1)}' "$EXPORT_CONF" | tail -1)"
TOKEN_PATH="${TOKEN_PATH:-/etc/pandok-gateway/aws-export-token}"
if [[ ! -f "$TOKEN_PATH" ]]; then
  echo "ERROR: configured AWS export token file is missing." >&2
  exit 1
fi
if ! sudo -u pandok test -r "$TOKEN_PATH"; then
  echo "ERROR: pandok service user cannot read the configured AWS export token file." >&2
  exit 1
fi

# Fetch and pin exact canonical contract.
python3 sync_exact_contract.py "$CONTRACT"

# Install runtime dependency needed by the candidate tests and deployed app.
sudo "$VENV/bin/python" -m pip install "jsonschema==4.26.0"

# Isolated tests: no production DB, keys, endpoint, or player data are used.
PANDOK_TEST_SCHEMA_PATH="$CONTRACT" "$VENV/bin/python" test_gateway_v2.py
"$VENV/bin/python" test_gateway_v2_export.py
"$VENV/bin/python" synthetic_gateway_to_aws_e2e.py

# Back up current active entry point and existing contract if present.
sudo cp "$APP_DIR/app_phase2_8.py" "$APP_DIR/app_phase2_8.py.pre-v2-aws-export_$STAMP"
if [[ -f "$APP_DIR/telemetry-event-v2.schema.json" ]]; then
  sudo cp "$APP_DIR/telemetry-event-v2.schema.json" "$APP_DIR/telemetry-event-v2.schema.json.pre-v2-aws-export_$STAMP"
fi

# Install source + exact schema.
sudo install -o root -g root -m 0644 "$STAGE_DIR/app_phase2_8.py" "$APP_DIR/app_phase2_8.py"
sudo install -o root -g root -m 0644 "$CONTRACT" "$APP_DIR/telemetry-event-v2.schema.json"

# Add export config to the service without embedding endpoint/token in the service unit.
sudo mkdir -p "$DROPIN_DIR"
printf '%s\n' '[Service]' "EnvironmentFile=$EXPORT_CONF" | sudo tee "$DROPIN" >/dev/null
sudo systemctl daemon-reload

# Syntax check and restart.
cd "$APP_DIR"
sudo "$VENV/bin/python" -m py_compile app_phase2_8.py
sudo systemctl restart pandok-gateway.service
sudo systemctl is-active --quiet pandok-gateway.service

# Verify v2 + export are live, without printing endpoint or credentials.
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
    body=json.load(r)
assert body["status"]=="ok", body
assert body["telemetry_contract"]=="2.0", body
assert body["real_aws_export"] is True, body
assert body["aws_export_configured"] is True, body
print(json.dumps(body, indent=2))
PY

echo "DEPLOYED: exact telemetry-event-v2 + AWS export implementation is active."
echo "Backup entry point: $APP_DIR/app_phase2_8.py.pre-v2-aws-export_$STAMP"
echo "Next: run a synthetic Run against the NON-PRODUCTION AWS test destination, then run post_deploy_capture.sh."
