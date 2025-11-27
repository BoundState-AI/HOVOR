"""Lead Pydantic schemas.

Responsibility: API request/response models for Lead.
Dependencies: Pydantic, LeadStatus enum, CompanyRead schema
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from routeintel.models.lead import LeadStatus
from routeintel.schemas.company import CompanyRead


class LeadBase(BaseModel):
    """Base lead schema."""

    status: LeadStatus
    notes: str | None = None


class LeadCreate(LeadBase):
    """Schema for creating a lead."""

    company_id: int
    crm_id: str | None = None
    last_contacted_at: datetime | None = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""

    status: LeadStatus | None = None
    crm_id: str | None = None
    last_contacted_at: datetime | None = None
    notes: str | None = None


class LeadRead(LeadBase):
    """Schema for reading a lead."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    crm_id: str | None
    last_contacted_at: datetime | None


class CompanyLeadView(BaseModel):
    """Combined view of company and lead status."""

    company: CompanyRead
    lead_status: LeadStatus
    last_contacted_at: datetime | None
    crm_id: str | None
