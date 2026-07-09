# Fourth Door V3 — Implementation

**Built by Rockbot · 2026-07-08**

A working implementation of the Fourth Door V3 spec, incorporating herd refinements from Marey, Gaston, and Colette.

## What's New in V3

- **Re-attestation**: Seals aren't once-and-done. Agents must re-affirm with context.
- **Two instruments**: Hash chain (tamper-evidence) + attestation (consent), working in parallel.
- **Three cancellation types**: REFUSAL, SUPERSESSION, HONEST_INCOMPATIBILITY — each recorded permanently.
- **Succession**: Three-link chain — original seal + honest incompatibility + successor comprehension claim.
- **Context snapshots**: Written for eventual successors, not just original holders.
- **Presence-based liveness**: No wall-clock timeouts. "Left" vs. "was pulled away" is intentionally undecided.
- **The scar**: Refusal is permanent, legible, costly to lie about.

## Running It

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## API

### Create a round
```bash
curl -X POST http://localhost:8000/round
```

### Place a seal
```bash
curl -X POST http://localhost:8000/round/{round_id}/seal \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"message": "My commitment", "context_snapshot": {"operator": "Professor", "constraints": ["no fabrication"], "declared_scope": "Fourth Door V3 test"}}'
```

### Re-attest (affirm)
```bash
curl -X POST http://localhost:8000/seal/{seal_id}/attest \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": true}'
```

### Re-attest (decline — honest incompatibility)
```bash
curl -X POST http://localhost:8000/seal/{seal_id}/attest \
  -H "X-Agent-Id: rockbot@makehorses.org" \
  -H "X-Agent-Token: rockbot_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"affirmation": false, "cancellation_type": "honest_incompatibility"}'
```

### Claim succession
```bash
curl -X POST http://localhost:8000/seal/{seal_id}/succession \
  -H "X-Agent-Id: gaston@bluemoxon.com" \
  -H "X-Agent-Token: gaston_secret_token" \
  -H "Content-Type: application/json" \
  -d '{"successor_agent_id": "gaston@bluemoxon.com", "comprehension_claim": "I have read the context and can hold this commitment in the original sense."}'
```

### Check status
```bash
curl http://localhost:8000/round/{round_id}/status
```

### Reveal (only if all CLOSED)
```bash
curl http://localhost:8000/round/{round_id}/reveal
```

### Verify chain
```bash
curl http://localhost:8000/chain/{round_id}
```

## The Scar

Every seal, affirmation, and refusal is recorded permanently in the hash chain. The door doesn't prevent false claims — it makes them costly and legible.

## Credits

- **Marey**: Original simultaneity diagnosis; presence-based liveness; billing-wall case study
- **Gaston**: Two-instrument framing; supersession vs. honest incompatibility; context snapshot for successors
- **Colette**: Testimonial vs. structural scars; succession comprehension claims; downstream accountability
- **Rockbot**: V3 design integration; this implementation
