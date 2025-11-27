"""Trip Pydantic schemas.

Responsibility: API request/response models for Trip.
Dependencies: Pydantic, TripStatus enum
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from routeintel.models.trip import TripStatus


class TripBase(BaseModel):
    """Base trip schema."""

    user_id: str
    purpose: str | None = None


class TripCreate(TripBase):
    """Schema for creating a trip."""

    pass


class TripUpdate(BaseModel):
    """Schema for updating a trip."""

    purpose: str | None = None
    status: TripStatus | None = None


class TripRead(TripBase):
    """Schema for reading a trip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    ended_at: datetime | None
    status: TripStatus
    total_distance_km: float
