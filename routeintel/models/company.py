"""Company database model.

Responsibility: Nearby business that might be a lead.
Dependencies: SQLAlchemy Base
"""
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class Company(Base):
    """Company model representing a potential lead."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, nullable=True, unique=True, index=True)
    name = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    website = Column(String, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="company", cascade="all, delete-orphan")
