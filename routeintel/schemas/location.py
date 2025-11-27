"""Location Pydantic schemas.

Responsibility: API request/response models for Location.
Dependencies: Pydantic
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    """Base location schema."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: float | None = Field(None, ge=0)


class LocationCreate(LocationBase):
    """Schema for creating a location."""

    timestamp: datetime | None = None


class LocationRead(LocationBase):
    """Schema for reading a location."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    timestamp: datetime
    is_stop: bool
