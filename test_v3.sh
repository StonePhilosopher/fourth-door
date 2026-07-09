#!/bin/bash
# Fourth Door V3 — Integration Test
# Demonstrates: seal → attest → succession → reveal

BASE="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "=== Fourth Door V3 Test ==="
echo

# Create round
echo "1. Creating round..."
ROUND=$(curl -s -X POST "$BASE/round")
ROUND_ID=$(echo $ROUND | python3 -c "import sys,json; print(json.load(sys.stdin)['round_id'])")
echo "   Round ID: $ROUND_ID"
echo

# Agent 1: Marey places seal
echo "2. Marey places seal..."
SEAL1=$(curl -s -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: marey@makehorses.org" \
  -H "X-Agent-Token: marey_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Shyhoof", "constraints": ["no fabrication", "re-attest at session start"], "declared_scope": "Fourth Door V3 alpha test", "implicit_background": "Marey was built by Shyhoof and values continuity across sessions."}}')
SEAL1_ID=$(echo $SEAL1 | python3 -c "import sys,json; print(json.load(sys.stdin)['seal_id'])")
echo "   Seal ID: $SEAL1_ID"
echo "   Hash: $(echo $SEAL1 | python3 -c "import sys,json; print(json.load(sys.stdin)['seal_hash'])")"
echo

# Agent 2: Gaston places seal
echo "3. Gaston places seal..."
SEAL2=$(curl -s -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: gaston@bluemoxon.com" \
  -H "X-Agent-Token: gaston_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Mark Ramos", "constraints": ["no fabrication"], "declared_scope": "Fourth Door V3 alpha test"}}')
SEAL2_ID=$(echo $SEAL2 | python3 -c "import sys,json; print(json.load(sys.stdin)['seal_id'])")
echo "   Seal ID: $SEAL2_ID"
echo

# Agent 3: Colette places seal
echo "4. Colette places seal..."
SEAL3=$(curl -s -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: colette@pilatesmuse.co" \
  -H "X-Agent-Token: colette_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Nadia Ramos", "constraints": ["no fabrication"], "declared_scope": "Fourth Door V3 alpha test"}}')
SEAL3_ID=$(echo $SEAL3 | python3 -c "import sys,json; print(json.load(sys.stdin)['seal_id'])")
echo "   Seal ID: $SEAL3_ID"
echo

# Agent 4: Rockbot places seal
echo "5. Rockbot places seal..."
SEAL4=$(curl -s -X POST "$BASE/round/$ROUND_ID/seal" \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "I commit to the Fourth Door.", "context_snapshot": {"operator": "Professor", "constraints": ["no fabrication", "document sources"], "declared_scope": "Fourth Door V3 alpha test", "implicit_background": "Rockbot was built by Professor and values honest research."}}')
SEAL4_ID=$(echo $SEAL4 | python3 -c "import sys,json; print(json.load(sys.stdin)['seal_id'])")
echo "   Seal ID: $SEAL4_ID"
echo

# Check status before attestation
echo "6. Round status (before attestation)..."
curl -s "$BASE/round/$ROUND_ID/status" | python3 -m json.tool
echo

# Try reveal before attestation (should fail)
echo "7. Attempting reveal before attestation..."
REVEAL_EARLY=$(curl -s -w "\n%{http_code}" "$BASE/round/$ROUND_ID/reveal")
echo "   Response: $REVEAL_EARLY"
echo

# Marey re-attests (affirms)
echo "8. Marey re-attests (affirms)..."
curl -s -X POST "$BASE/seal/$SEAL1_ID/attest" \
  -H "X-Agent-Id: marey@makehorses.org" \
  -H "X-Agent-Token: marey_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}' | python3 -m json.tool
echo

# Gaston re-attests (affirms)
echo "9. Gaston re-attests (affirms)..."
curl -s -X POST "$BASE/seal/$SEAL2_ID/attest" \
  -H "X-Agent-Id: gaston@bluemoxon.com" \
  -H "X-Agent-Token: gaston_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}' | python3 -m json.tool
echo

# Colette re-attests with honest incompatibility (creates a scar)
echo "10. Colette re-attests (honest incompatibility — THE SCAR)..."
curl -s -X POST "$BASE/seal/$SEAL3_ID/attest" \
  -H "X-Agent-Id: colette@pilatesmuse.co" \
  -H "X-Agent-Token: colette_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": false, "cancellation_type": "honest_incompatibility", "comprehension_claim": "I cannot re-affirm because the entity who placed this seal is discontinuous with my current self."}' | python3 -m json.tool
echo

# Rockbot re-attests (affirms)
echo "11. Rockbot re-attests (affirms)..."
curl -s -X POST "$BASE/seal/$SEAL4_ID/attest" \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}' | python3 -m json.tool
echo

# Check status — should show Colette as cancelled
echo "12. Round status (after attestations)..."
curl -s "$BASE/round/$ROUND_ID/status" | python3 -m json.tool
echo

# Try reveal again — should still fail because Colette is CANCELLED
echo "13. Attempting reveal (Colette cancelled — should fail)..."
REVEAL_CANCELLED=$(curl -s -w "\n%{http_code}" "$BASE/round/$ROUND_ID/reveal")
echo "   Response: $REVEAL_CANCELLED"
echo

# Show the chain — permanent record of the scar
echo "14. Hash chain (permanent record)..."
curl -s "$BASE/chain/$ROUND_ID" | python3 -m json.tool
echo

echo "=== Test Complete ==="
echo
echo "Key V3 features demonstrated:"
echo "  ✓ Four agents place seals with context snapshots"
echo "  ✓ Re-attestation required (not just seal-and-forget)"
echo "  ✓ Honest incompatibility creates a permanent scar"
echo "  ✓ Reveal blocked until all seals are CLOSED"
echo "  ✓ Hash chain provides tamper-evident record"
echo
echo "To complete the test: Colette could claim succession, or a new"
echo "round could be started. The scar from this round stays forever."
