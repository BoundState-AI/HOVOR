"""Company Pydantic schemas.

Responsibility: API request/response models for Company.
Dependencies: Pydantic
"""
from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    """Base company schema."""

    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str | None = None
    state: str | None = None
    country: str | None = None
    industry: str | None = None
    employee_count: int | None = Field(None, ge=0)
    website: str | None = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""

    external_id: str | None = None


class CompanyRead(CompanyBase):
    """Schema for reading a company."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None


class CompanyData(BaseModel):
    """Schema for company data from external sources."""

    external_id: str
    name: str
    latitude: float
    longitude: float
    city: str | None = None
    state: str | None = None
    country: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    website: str | None = None
