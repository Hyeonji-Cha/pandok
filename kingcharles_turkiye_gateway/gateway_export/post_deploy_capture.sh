#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-/tmp/pandok-v2-export-deployed-sanitized}"
rm -rf "$OUT"; mkdir -p "$OUT/source" "$OUT/verification"
cd /opt/pandok-gateway
cp app_phase2_8.py telemetry-event-v2.schema.json "$OUT/source/"
sha256sum app_phase2_8.py telemetry-event-v2.schema.json > "$OUT/verification/SHA256SUMS.txt"
{
  echo "service:"
  systemctl show pandok-gateway.service -p WorkingDirectory -p ExecStart -p User -p Group --no-pager
  echo
  echo "health:"
  curl -fsS http://127.0.0.1:8000/health
  echo
  echo "access-log check:"
  systemctl show pandok-gateway.service -p ExecStart --no-pager | grep -- '--no-access-log' >/dev/null && echo PASS || echo FAIL
  echo
  echo "git:"
  git rev-parse HEAD 2>/dev/null || echo "NOT A GIT WORKTREE; use SHA256SUMS.txt as deployed version identifier"
} > "$OUT/verification/DEPLOYED_STATUS.txt"
# Never copy token/key/config files, database files, environment dumps, IPs, or logs.
tar -C "$(dirname "$OUT")" -czf "${OUT}.tar.gz" "$(basename "$OUT")"
echo "Created sanitized deployed capture: ${OUT}.tar.gz"
