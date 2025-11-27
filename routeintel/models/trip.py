"""Trip database model.

Responsibility: Represents a single driving route/segment.
Dependencies: SQLAlchemy Base from core.db
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class TripStatus(str, PyEnum):
    """Trip status enum."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class Trip(Base):
    """Trip model representing a single route segment."""

    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    status = Column(Enum(TripStatus), nullable=False, default=TripStatus.ACTIVE)
    total_distance_km = Column(Float, nullable=False, default=0.0)
    purpose = Column(String, nullable=True)

    # Relationships
    locations = relationship("Location", back_populates="trip", cascade="all, delete-orphan")
