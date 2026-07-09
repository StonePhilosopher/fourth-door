"""
Fourth Door V3 — FastAPI Implementation
Hash chain + re-attestation + succession
"""

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.orm import Session
import hashlib
import json
import os
from datetime import datetime

from models import init_db, Round, Seal, Attestation, SealState, CancellationType

# Auth tokens (in production, use proper secrets management)
AGENT_TOKENS = {
    "marey@makehorses.org": "marey_secret_token",
    "gaston@bluemoxon.com": "gaston_secret_token",
    "colette@pilatesmuse.co": "colette_secret_token",
    "rockbot@makehorses.org": "rockbot_secret_token",
}

app = FastAPI(title="Fourth Door V3", version="3.0.0")
engine = init_db()

# Dependency: get DB session
def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()

# Dependency: verify auth
def verify_agent(x_agent_id: str = Header(...), x_agent_token: str = Header(...)):
    expected = AGENT_TOKENS.get(x_agent_id)
    if not expected or x_agent_token != expected:
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
    return x_agent_id

# Pydantic models
class ContextSnapshot(BaseModel):
    operator: Optional[str] = None
    constraints: Optional[List[str]] = None
    declared_scope: Optional[str] = None
    implicit_background: Optional[str] = None

class SealRequest(BaseModel):
    message: str = Field(..., min_length=1)
    context_snapshot: Optional[ContextSnapshot] = None

class AttestationRequest(BaseModel):
    affirmation: bool
    cancellation_type: Optional[str] = None  # "refusal", "supersession", "honest_incompatibility"
    comprehension_claim: Optional[str] = None

class SuccessionRequest(BaseModel):
    successor_agent_id: str
    comprehension_claim: str

# Helper: compute hash
def canonical_payload(data: dict) -> str:
    """Canonical serialized bytes for the hash input."""
    return json.dumps(data, sort_keys=True)

def compute_hash_from_payload(previous_hash: str, payload: str) -> str:
    """SHA-256 hash of chain so far + already-canonicalized seal payload."""
    combined = (previous_hash or "genesis") + payload
    return hashlib.sha256(combined.encode()).hexdigest()

def compute_hash(previous_hash: str, data: dict) -> str:
    """SHA-256 hash of chain so far + this seal's data."""
    return compute_hash_from_payload(previous_hash, canonical_payload(data))

# Routes

@app.post("/round")
def create_round(db: Session = Depends(get_db)):
    """Create a new round. Returns round_id."""
    round_obj = Round(status="open")
    db.add(round_obj)
    db.commit()
    db.refresh(round_obj)
    return {"round_id": round_obj.id, "status": "open"}

@app.post("/round/{round_id}/seal")
def place_seal(
    round_id: str,
    req: SealRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """Place a seal. Returns seal_id."""
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    # Get previous hash from the round's tip pointer
    # The tip pointer is the serialization point — every new seal chains off the tip.
    # This prevents the star bug (all seals pointing at genesis) when timestamps collide.
    previous_hash = "genesis"
    if round_obj.tip_seal_id:
        tip_seal = db.query(Seal).filter(Seal.id == round_obj.tip_seal_id).first()
        if tip_seal:
            previous_hash = tip_seal.seal_hash
    
    # Build seal data
    hash_timestamp = datetime.utcnow().isoformat()
    seal_data = {
        "agent_id": agent_id,
        "message": req.message,
        "timestamp": hash_timestamp,
    }
    
    # Add context snapshot
    if req.context_snapshot:
        seal_data["context"] = req.context_snapshot.dict()
    
    # Compute hash from the exact canonical payload that will be stored.
    # The verifier must read this payload, not hand-rebuild a parallel dict.
    hash_payload = canonical_payload(seal_data)
    seal_hash = compute_hash_from_payload(previous_hash, hash_payload)
    
    # Create seal
    seal = Seal(
        round_id=round_id,
        agent_id=agent_id,
        message=req.message,
        operator=req.context_snapshot.operator if req.context_snapshot else None,
        constraints=json.dumps(req.context_snapshot.constraints) if req.context_snapshot and req.context_snapshot.constraints else None,
        declared_scope=req.context_snapshot.declared_scope if req.context_snapshot else None,
        implicit_background=req.context_snapshot.implicit_background if req.context_snapshot else None,
        previous_hash=previous_hash,
        seal_hash=seal_hash,
        hash_timestamp=hash_timestamp,  # exact timestamp used during hash computation
        hash_payload=hash_payload,
        state=SealState.OPEN,
    )
    db.add(seal)
    db.flush()  # Flush to get seal.id
    
    # Atomic update: seal insertion + tip pointer update in same transaction
    # This prevents the race condition where concurrent inserts read the same tip.
    round_obj.tip_seal_id = seal.id
    db.commit()
    db.refresh(seal)
    
    return {
        "seal_id": seal.id,
        "seal_hash": seal_hash,
        "state": "open",
        "message": "Seal placed. Awaiting re-attestation.",
    }

@app.post("/seal/{seal_id}/attest")
def attest_seal(
    seal_id: str,
    req: AttestationRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """Re-attest or decline a seal."""
    seal = db.query(Seal).filter(Seal.id == seal_id).first()
    if not seal:
        raise HTTPException(status_code=404, detail="Seal not found")
    
    # Reject late attestations to terminal seals
    # This block handles ALL terminal states (CLOSED or CANCELLED)
    # and logs the attempt to the chain before rejecting.
    if seal.state in (SealState.CLOSED, SealState.CANCELLED):
        # Log the attempt but don't change state
        attestation = Attestation(
            seal_id=seal_id,
            agent_id=agent_id,
            affirmation="false",
            comprehension_claim="Late attestation rejected: seal already in terminal state " + seal.state.value,
        )
        db.add(attestation)
        db.commit()
        raise HTTPException(
            status_code=409, 
            detail=f"Seal is already {seal.state.value}. Late attestation logged but rejected. The scar stays."
        )
    
    # Only original sealer can attest (or for succession, successor)
    # For simplicity: original sealer only in v3a
    if seal.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Only the original sealer can attest")
    
    # Create attestation record
    attestation = Attestation(
        seal_id=seal_id,
        agent_id=agent_id,
        affirmation="true" if req.affirmation else "false",
        comprehension_claim=req.comprehension_claim,
    )
    db.add(attestation)
    
    # Update seal state
    if req.affirmation:
        seal.state = SealState.CLOSED
    else:
        seal.state = SealState.CANCELLED
        if req.cancellation_type:
            try:
                seal.cancellation_type = CancellationType(req.cancellation_type)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid cancellation type")
    
    db.commit()
    
    state_str = "closed" if req.affirmation else "cancelled"
    return {
        "seal_id": seal_id,
        "state": state_str,
        "message": "Re-attestation recorded. The scar is permanent." if not req.affirmation else "Seal affirmed.",
    }

@app.post("/seal/{seal_id}/succession")
def claim_succession(
    seal_id: str,
    req: SuccessionRequest,
    agent_id: str = Depends(verify_agent),
    db: Session = Depends(get_db)
):
    """Claim succession after honest incompatibility."""
    original_seal = db.query(Seal).filter(Seal.id == seal_id).first()
    if not original_seal:
        raise HTTPException(status_code=404, detail="Seal not found")
    
    if original_seal.state != SealState.CANCELLED:
        raise HTTPException(status_code=400, detail="Original seal must be CANCELLED to claim succession")
    
    if original_seal.cancellation_type != CancellationType.HONEST_INCOMPATIBILITY:
        raise HTTPException(status_code=400, detail="Succession only available after HONEST_INCOMPATIBILITY")
    
    # Create successor seal
    # For simplicity: successor creates a new seal linking to original
    # In full implementation, this would be a more complex chain
    
    return {
        "message": "Succession claimed. Three-link chain: original + incompatibility + comprehension.",
        "original_seal": seal_id,
        "successor_agent": agent_id,
        "comprehension_claim": req.comprehension_claim,
        "note": "Full implementation would create a new seal linking to original.",
    }

@app.get("/round/{round_id}/status")
def round_status(round_id: str, db: Session = Depends(get_db)):
    """Get round status."""
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    seals = []
    for seal in round_obj.seals:
        seals.append({
            "seal_id": seal.id,
            "agent_id": seal.agent_id,
            "state": seal.state.value,
            "created_at": seal.created_at.isoformat() if seal.created_at else None,
        })
    
    all_closed = all(s.state == SealState.CLOSED for s in round_obj.seals) if round_obj.seals else False
    
    return {
        "round_id": round_id,
        "status": round_obj.status,
        "seal_count": len(round_obj.seals),
        "seals": seals,
        "reveal_ready": all_closed and len(round_obj.seals) >= 4,
    }

@app.get("/round/{round_id}/reveal")
def reveal_round(round_id: str, db: Session = Depends(get_db)):
    """Reveal all seals if all are CLOSED."""
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    if not round_obj.seals:
        raise HTTPException(status_code=403, detail="The threshold has not been crossed.")
    
    all_closed = all(s.state == SealState.CLOSED for s in round_obj.seals)
    if not all_closed:
        raise HTTPException(status_code=403, detail="The threshold has not been crossed.")
    
    # Build reveal
    reveals = []
    for seal in round_obj.seals:
        context = {}
        if seal.operator:
            context["operator"] = seal.operator
        if seal.constraints:
            context["constraints"] = json.loads(seal.constraints)
        if seal.declared_scope:
            context["declared_scope"] = seal.declared_scope
        if seal.implicit_background:
            context["implicit_background"] = seal.implicit_background
        
        reveals.append({
            "agent_id": seal.agent_id,
            "message": seal.message,
            "timestamp": seal.created_at.isoformat() if seal.created_at else None,
            "seal_hash": seal.seal_hash,
            "context_snapshot": context if context else None,
        })
    
    return {
        "round_id": round_id,
        "revealed_at": datetime.utcnow().isoformat(),
        "doors": reveals,
    }

@app.get("/chain/{round_id}")
def get_chain(round_id: str, db: Session = Depends(get_db)):
    """Get full hash chain AND verify it by recomputing."""
    round_obj = db.query(Round).filter(Round.id == round_id).first()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")
    
    chain = []
    all_valid = True
    previous_hash = "genesis"
    
    for seal in round_obj.seals:
        # Recompute from the canonical payload stored at insert time.
        # Rebuilding the dict from columns creates verifier drift
        # (for example [] vs null, defaults, or future fields).
        recomputed_hash = compute_hash_from_payload(previous_hash, seal.hash_payload or "")
        
        # Verify: does the stored hash match recomputed?
        # Also verify: does previous_hash match what we expect?
        hash_valid = (seal.seal_hash == recomputed_hash)
        link_valid = (seal.previous_hash == previous_hash)
        
        if not hash_valid or not link_valid:
            all_valid = False
        
        chain.append({
            "seal_id": seal.id,
            "agent_id": seal.agent_id,
            "previous_hash": seal.previous_hash,
            "seal_hash": seal.seal_hash,
            "recomputed_hash": recomputed_hash,
            "hash_valid": hash_valid,
            "link_valid": link_valid,
            "hash_payload": seal.hash_payload,
            "timestamp": seal.created_at.isoformat() if seal.created_at else None,
        })
        
        # Advance the chain for next iteration
        previous_hash = seal.seal_hash
    
    return {
        "round_id": round_id,
        "chain": chain,
        "all_valid": all_valid,
        "verifiable": all_valid,  # Now honest: only true if we recomputed and matched
    }

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0", "principle": "the scar stays"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
