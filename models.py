"""
Fourth Door V3 — Database Models
SQLAlchemy ORM for SQLite backend
"""

from sqlalchemy import create_engine, Column, String, DateTime, Enum, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Session
from sqlalchemy.sql import func
import enum
import uuid

Base = declarative_base()

class SealState(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"

class CancellationType(enum.Enum):
    REFUSAL = "refusal"
    SUPERSESSION = "supersession"
    HONEST_INCOMPATIBILITY = "honest_incompatibility"

class Round(Base):
    __tablename__ = "rounds"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String, default="open")  # open, ready, revealed
    
    seals = relationship("Seal", back_populates="round", order_by="Seal.created_at")

class Seal(Base):
    __tablename__ = "seals"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    round_id = Column(String, ForeignKey("rounds.id"))
    agent_id = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    
    # Context snapshot (written for successor, not just original holder)
    operator = Column(String)
    constraints = Column(Text)  # JSON array as string
    declared_scope = Column(Text)
    implicit_background = Column(Text)
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Hash chain
    previous_hash = Column(String)
    seal_hash = Column(String, nullable=False, unique=True)
    
    # State machine
    state = Column(Enum(SealState), default=SealState.OPEN)
    cancellation_type = Column(Enum(CancellationType))
    
    # Succession
    successor_seal_id = Column(String, ForeignKey("seals.id"), nullable=True)
    
    round = relationship("Round", back_populates="seals")
    attestations = relationship("Attestation", back_populates="seal", order_by="Attestation.created_at")
    successor_seal = relationship("Seal", remote_side=[id])

class Attestation(Base):
    __tablename__ = "attestations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    seal_id = Column(String, ForeignKey("seals.id"))
    agent_id = Column(String, nullable=False)
    affirmation = Column(String, nullable=False)  # "true" or "false"
    comprehension_claim = Column(Text)  # for succession
    created_at = Column(DateTime, server_default=func.now())
    
    seal = relationship("Seal", back_populates="attestations")

# Create tables
def init_db(db_path="fourth_door.db"):
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    return engine
