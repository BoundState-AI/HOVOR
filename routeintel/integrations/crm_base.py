"""CRM client abstract interface.

Responsibility: Define contract for CRM integrations.
Dependencies: Protocol, CompanyData schema
SOLID: Interface Segregation - minimal, focused interface for CRM operations.
        Dependency Inversion - high-level services depend on this abstraction.
"""
from typing import Protocol
from pydantic import BaseModel

from routeintel.models.company import Company


class CRMCompany(BaseModel):
    """CRM company representation."""

    crm_id: str
    name: str
    domain: str | None = None
    status: str


class CRMClient(Protocol):
    """Abstract interface for CRM clients."""

    async def find_company_by_name(self, name: str) -> CRMCompany | None:
        """Find company in CRM by name."""
        ...

    async def find_company_by_domain(self, domain: str) -> CRMCompany | None:
        """Find company in CRM by domain."""
        ...

    async def create_lead(self, company: Company) -> str:
        """Create a new lead in CRM, returns CRM ID."""
        ...
