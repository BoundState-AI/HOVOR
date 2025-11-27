"""Lead database model.

Responsibility: Relationship between user and a company.
Dependencies: SQLAlchemy Base, Company model
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class LeadStatus(str, PyEnum):
    """Lead status enum."""

    CUSTOMER = "CUSTOMER"
    PROSPECT = "PROSPECT"
    NEW = "NEW"


class Lead(Base):
    """Lead model representing the relationship between user and company."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    crm_id = Column(String, nullable=True, unique=True, index=True)
    status = Column(Enum(LeadStatus), nullable=False, default=LeadStatus.NEW)
    last_contacted_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="leads")
