from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Role(Base):
    """
    Defines hierarchical roles and scalable RBAC permissions via JSONB.
    """
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String, unique=True, nullable=False)
    permissions = Column(JSONB, nullable=False, default={})
    
    users = relationship("User", back_populates="role")

class User(Base):
    """
    Core user model managing identity, balances, and encrypted API keys.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    profile_image = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    credits = Column(Integer, default=0, nullable=False)
    encrypted_api_keys = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    role = relationship("Role", back_populates="users")
    usages = relationship("Usage", back_populates="user")
    payments = relationship("Payment", back_populates="user")

class Usage(Base):
    """
    Immutable audit log of AI interactions and token consumption.
    """
    __tablename__ = "usage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    prompt = Column(String, nullable=False)
    response_tokens = Column(Integer, nullable=False, default=0)
    credits_used = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="usages")

class Payment(Base):
    """
    Tracks subscription tiers and monetary transactions.
    """
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_status = Column(String, nullable=False) # e.g., 'successful', 'pending'
    credits_added = Column(Integer, nullable=False)
    plan_type = Column(String, nullable=False)
    
    user = relationship("User", back_populates="payments")