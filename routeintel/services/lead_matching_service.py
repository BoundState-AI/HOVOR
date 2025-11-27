"""Lead matching service implementation.

Responsibility: Match companies to CRM records and determine lead status.
Dependencies: SQLAlchemy Session, CRMClient protocol, Company/Lead models
SOLID: Dependency Inversion - depends on CRMClient abstraction.
        Single Responsibility - only handles CRM matching logic.

Engineering notes:
- Attempts matching by domain first, then by name
- Maps CRM status to internal LeadStatus enum
- Creates/updates local Lead records for tracking
- Does not create CRM records (that's CRMSyncService's job)
"""
from sqlalchemy.orm import Session

from routeintel.models.company import Company
from routeintel.models.lead import Lead, LeadStatus
from routeintel.integrations.crm_base import CRMClient
from routeintel.schemas.lead import CompanyLeadView
from routeintel.schemas.company import CompanyRead


class LeadMatchingService:
    """Service for matching companies to CRM and determining lead status."""

    def __init__(self, db: Session, crm_client: CRMClient) -> None:
        """Initialize service with database and CRM client."""
        self.db = db
        self.crm_client = crm_client

    async def match_companies_to_crm(
        self,
        companies: list[Company],
    ) -> list[CompanyLeadView]:
        """Match companies to CRM and return lead views.

        Args:
            companies: List of companies to match

        Returns:
            List of company-lead views with status
        """
        result = []

        for company in companies:
            crm_company = None

            if company.website:
                crm_company = await self.crm_client.find_company_by_domain(
                    company.website
                )

            if not crm_company:
                crm_company = await self.crm_client.find_company_by_name(
                    company.name
                )

            if crm_company:
                lead = self._get_or_create_lead(company, crm_company.crm_id)
                lead.status = self._map_crm_status_to_lead_status(crm_company.status)
                self.db.commit()
                self.db.refresh(lead)

                result.append(
                    CompanyLeadView(
                        company=CompanyRead.model_validate(company),
                        lead_status=lead.status,
                        last_contacted_at=lead.last_contacted_at,
                        crm_id=lead.crm_id,
                    )
                )
            else:
                lead = self._get_or_create_lead(company, None)
                result.append(
                    CompanyLeadView(
                        company=CompanyRead.model_validate(company),
                        lead_status=LeadStatus.NEW,
                        last_contacted_at=None,
                        crm_id=None,
                    )
                )

        return result

    def _get_or_create_lead(self, company: Company, crm_id: str | None) -> Lead:
        """Get existing lead or create new one."""
        existing = (
            self.db.query(Lead).filter(Lead.company_id == company.id).first()
        )

        if existing:
            if crm_id and not existing.crm_id:
                existing.crm_id = crm_id
            return existing

        lead = Lead(
            company_id=company.id,
            crm_id=crm_id,
            status=LeadStatus.NEW,
        )
        self.db.add(lead)
        self.db.commit()
        self.db.refresh(lead)
        return lead

    @staticmethod
    def _map_crm_status_to_lead_status(crm_status: str) -> LeadStatus:
        """Map CRM status string to internal LeadStatus enum."""
        status_map = {
            "CUSTOMER": LeadStatus.CUSTOMER,
            "PROSPECT": LeadStatus.PROSPECT,
        }
        return status_map.get(crm_status, LeadStatus.NEW)
