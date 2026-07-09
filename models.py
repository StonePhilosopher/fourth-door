"""
Fourth Door V3 — Database Models
SQLAlchemy ORM for SQLite backend
"""

from sqlalchemy import create_engine, Column, String, DateTime, Enum, Text, ForeignKey, event
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
    
    # Tip pointer: explicit serialization point for the hash chain
    # The tip_seal_id is the latest seal in this round.
    # Every new seal chains off the tip, making the chain a chain, not a star.
    tip_seal_id = Column(String, ForeignKey("seals.id"), nullable=True)
    
    seals = relationship("Seal", back_populates="round", foreign_keys="Seal.round_id", order_by="Seal.created_at")
    tip_seal = relationship("Seal", foreign_keys=[tip_seal_id])

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
    
    round = relationship("Round", back_populates="seals", foreign_keys=[round_id])
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
    
    # BEGIN IMMEDIATE: take write lock at transaction start, before any reads.
    # This serializes the entire read-compute-write sequence for seal placement,
    # preventing the concurrent-read race that creates a star chain.
    # Marey (2026-07-08): "the write lock at the start of the transaction"
    @event.listens_for(engine, "begin")
    def _begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")
    
    Base.metadata.create_all(engine)
    return engine
