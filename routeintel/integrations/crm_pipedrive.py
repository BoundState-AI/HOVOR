"""Mock Pipedrive CRM client implementation.

Responsibility: Simulate CRM operations for demo/testing.
Dependencies: CRMClient protocol, CRMCompany schema
SOLID: Liskov Substitution - behaves identically to any real CRM client.
        Single Responsibility - only handles CRM data simulation.
"""
from routeintel.integrations.crm_base import CRMClient, CRMCompany
from routeintel.models.company import Company


class PipedriveCRMClient:
    """Mock Pipedrive CRM client using in-memory storage."""

    def __init__(self) -> None:
        """Initialize mock CRM with sample data."""
        self._companies: dict[str, CRMCompany] = {
            "acme-corp": CRMCompany(
                crm_id="crm_001",
                name="Acme Corporation",
                domain="acme.com",
                status="CUSTOMER",
            ),
            "techstart-inc": CRMCompany(
                crm_id="crm_002",
                name="TechStart Inc",
                domain="techstart.io",
                status="PROSPECT",
            ),
            "global-manufacturing": CRMCompany(
                crm_id="crm_003",
                name="Global Manufacturing Ltd",
                domain="globalmanuf.com",
                status="CUSTOMER",
            ),
        }
        self._next_id = 4

    async def find_company_by_name(self, name: str) -> CRMCompany | None:
        """Find company in mock CRM by name (case-insensitive)."""
        name_lower = name.lower()
        for crm_company in self._companies.values():
            if crm_company.name.lower() == name_lower:
                return crm_company
        return None

    async def find_company_by_domain(self, domain: str) -> CRMCompany | None:
        """Find company in mock CRM by domain."""
        domain_lower = domain.lower()
        for crm_company in self._companies.values():
            if crm_company.domain and crm_company.domain.lower() == domain_lower:
                return crm_company
        return None

    async def create_lead(self, company: Company) -> str:
        """Create a new lead in mock CRM."""
        crm_id = f"crm_{self._next_id:03d}"
        self._next_id += 1

        key = company.name.lower().replace(" ", "-")
        self._companies[key] = CRMCompany(
            crm_id=crm_id,
            name=company.name,
            domain=company.website,
            status="PROSPECT",
        )
        return crm_id


def get_crm_client() -> CRMClient:
    """Dependency injection factory for CRM client."""
    return PipedriveCRMClient()
