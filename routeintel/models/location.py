"""Location database model.

Responsibility: GPS breadcrumb tied to a trip.
Dependencies: SQLAlchemy Base, Trip model
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class Location(Base):
    """Location model representing GPS coordinates for a trip."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, nullable=True)
    is_stop = Column(Boolean, nullable=False, default=False)

    # Relationships
    trip = relationship("Trip", back_populates="locations")
