"""
Database models and setup
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid

Base = declarative_base()


class Trace(Base):
    """Trace model for observability"""
    __tablename__ = "traces"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, index=True)
    user_id = Column(String, index=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    total_latency_ms = Column(Float, default=0.0)
    status = Column(String, default="active")
    metadata = Column(JSON)


class Span(Base):
    """Span model for detailed tracing"""
    __tablename__ = "spans"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String, index=True)
    parent_span_id = Column(String, nullable=True)
    name = Column(String)
    span_type = Column(String)  # llm, retrieval, tool, agent
    input_data = Column(JSON)
    output_data = Column(JSON)
    tokens_used = Column(Integer)
    cost = Column(Float)
    latency_ms = Column(Float)
    status = Column(String)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON)


class SecurityIncident(Base):
    """Security incident model"""
    __tablename__ = "security_incidents"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    threat_type = Column(String, index=True)
    severity = Column(String, index=True)
    content_preview = Column(Text)
    trace_id = Column(String, nullable=True)
    user_id = Column(String, index=True, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="open")
    metadata = Column(JSON)


class Policy(Base):
    """Policy model"""
    __tablename__ = "policies"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    description = Column(Text, nullable=True)
    policy_type = Column(String, index=True)
    rules = Column(JSON)
    enabled = Column(Boolean, default=True)
    tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)
    version = Column(Integer, default=1)


def init_db(database_url: str):
    """Initialize database"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal
