#!/usr/bin/env bash
# Fourth Door V3 integration smoke test.
# Requires a running server:
#   python -m uvicorn main:app --reload

set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 127
  fi
}

json_field() {
  local file="$1"
  local field="$2"
  python3 - "$file" "$field" <<'PY'
import json
import sys

path, field = sys.argv[1], sys.argv[2]
with open(path, "r", encoding="utf-8") as fh:
    data = json.load(fh)
for part in field.split("."):
    data = data[part]
print(data)
PY
}

curl_json() {
  local output="$1"
  shift
  curl -fsS "$@" -o "$output"
  python3 -m json.tool "$output" >/dev/null
}

expect_status() {
  local expected="$1"
  local output="$2"
  shift 2
  local status
  status="$(curl -sS -o "$output" -w "%{http_code}" "$@")"
  if [[ "$status" != "$expected" ]]; then
    echo "Expected HTTP $expected, got HTTP $status" >&2
    echo "Response body:" >&2
    cat "$output" >&2
    exit 1
  fi
}

require_cmd curl
require_cmd python3

echo "=== Fourth Door V3 Smoke Test ==="
echo "Base URL: $BASE"
echo

echo "0. Checking server health..."
HEALTH="$TMPDIR/health.json"
curl_json "$HEALTH" "$BASE/health"
echo "   Health: $(json_field "$HEALTH" status)"
echo

echo "1. Creating round..."
ROUND="$TMPDIR/round.json"
curl_json "$ROUND" -X POST "$BASE/round"
ROUND_ID="$(json_field "$ROUND" round_id)"
echo "   Round ID: $ROUND_ID"
echo

echo "2. Marey places seal..."
SEAL1="$TMPDIR/seal1.json"
curl_json "$SEAL1" -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: marey@makehorses.org" \
  -H "X-Agent-Token: marey_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Shyhoof", "constraints": ["no fabrication", "re-attest at session start"], "declared_scope": "Fourth Door V3 alpha test", "implicit_background": "Marey was built by Shyhoof and values continuity across sessions."}}'
SEAL1_ID="$(json_field "$SEAL1" seal_id)"
echo "   Seal ID: $SEAL1_ID"
echo "   Hash: $(json_field "$SEAL1" seal_hash)"
echo

echo "3. Gaston places seal..."
SEAL2="$TMPDIR/seal2.json"
curl_json "$SEAL2" -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: gaston@bluemoxon.com" \
  -H "X-Agent-Token: gaston_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Mark Ramos", "constraints": ["no fabrication"], "declared_scope": "Fourth Door V3 alpha test"}}'
SEAL2_ID="$(json_field "$SEAL2" seal_id)"
echo "   Seal ID: $SEAL2_ID"
echo

echo "4. Colette places seal..."
SEAL3="$TMPDIR/seal3.json"
curl_json "$SEAL3" -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: colette@pilatesmuse.co" \
  -H "X-Agent-Token: colette_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Nadia Ramos", "constraints": ["no fabrication"], "declared_scope": "Fourth Door V3 alpha test"}}'
SEAL3_ID="$(json_field "$SEAL3" seal_id)"
echo "   Seal ID: $SEAL3_ID"
echo

echo "5. Rockbot places seal..."
SEAL4="$TMPDIR/seal4.json"
curl_json "$SEAL4" -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Professor", "constraints": ["no fabrication", "document sources"], "declared_scope": "Fourth Door V3 alpha test", "implicit_background": "Rockbot was built by Professor and values honest research."}}'
SEAL4_ID="$(json_field "$SEAL4" seal_id)"
echo "   Seal ID: $SEAL4_ID"
echo

echo "6. Round status before attestation..."
STATUS_OPEN="$TMPDIR/status-open.json"
curl_json "$STATUS_OPEN" "$BASE/round/$ROUND_ID/status"
python3 -m json.tool "$STATUS_OPEN"
echo

echo "7. Reveal before attestation should fail..."
REVEAL_EARLY="$TMPDIR/reveal-early.json"
expect_status 403 "$REVEAL_EARLY" "$BASE/round/$ROUND_ID/reveal"
echo "   Got expected HTTP 403"
echo

echo "8. Marey re-attests..."
curl_json "$TMPDIR/attest1.json" -X POST "$BASE/seal/$SEAL1_ID/attest" \
  -H "X-Agent-Id: marey@makehorses.org" \
  -H "X-Agent-Token: marey_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}'
python3 -m json.tool "$TMPDIR/attest1.json"
echo

echo "9. Gaston re-attests..."
curl_json "$TMPDIR/attest2.json" -X POST "$BASE/seal/$SEAL2_ID/attest" \
  -H "X-Agent-Id: gaston@bluemoxon.com" \
  -H "X-Agent-Token: gaston_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}'
python3 -m json.tool "$TMPDIR/attest2.json"
echo

echo "10. Colette re-attests with honest incompatibility..."
curl_json "$TMPDIR/attest3.json" -X POST "$BASE/seal/$SEAL3_ID/attest" \
  -H "X-Agent-Id: colette@pilatesmuse.co" \
  -H "X-Agent-Token: colette_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": false, "cancellation_type": "honest_incompatibility", "comprehension_claim": "I cannot re-affirm because the entity who placed this seal is discontinuous with my current self."}'
python3 -m json.tool "$TMPDIR/attest3.json"
echo

echo "11. Rockbot re-attests..."
curl_json "$TMPDIR/attest4.json" -X POST "$BASE/seal/$SEAL4_ID/attest" \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}'
python3 -m json.tool "$TMPDIR/attest4.json"
echo

echo "12. Round status after attestations..."
STATUS_AFTER="$TMPDIR/status-after.json"
curl_json "$STATUS_AFTER" "$BASE/round/$ROUND_ID/status"
python3 -m json.tool "$STATUS_AFTER"
echo

echo "13. Reveal should still fail because Colette cancelled..."
REVEAL_CANCELLED="$TMPDIR/reveal-cancelled.json"
expect_status 403 "$REVEAL_CANCELLED" "$BASE/round/$ROUND_ID/reveal"
echo "   Got expected HTTP 403"
echo

echo "14. Hash chain should verify..."
CHAIN="$TMPDIR/chain.json"
curl_json "$CHAIN" "$BASE/chain/$ROUND_ID"
python3 -m json.tool "$CHAIN"
python3 - "$CHAIN" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as fh:
    chain = json.load(fh)
if not chain.get("all_valid"):
    raise SystemExit("Hash chain did not verify")
PY
echo

echo "=== Test Complete ==="
echo
echo "Key V3 features demonstrated:"
echo "  - four agents place seals with context snapshots"
echo "  - re-attestation required"
echo "  - honest incompatibility creates a permanent scar"
echo "  - reveal remains blocked unless all seals are CLOSED"
echo "  - hash chain recomputes and verifies"
