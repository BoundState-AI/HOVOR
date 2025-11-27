"""CRM sync service implementation.

Responsibility: Orchestrate company discovery and CRM matching for trips.
Dependencies: CompanyDiscoveryService, LeadMatchingService
SOLID: Single Responsibility - only orchestrates existing services.
        Dependency Inversion - depends on service abstractions.

Engineering notes:
- Composes CompanyDiscoveryService and LeadMatchingService
- Provides single entry point for trip lead generation
- No direct DB or external service calls (delegates to injected services)
"""
from sqlalchemy.orm import Session

from routeintel.services.company_discovery_service import CompanyDiscoveryService
from routeintel.services.lead_matching_service import LeadMatchingService
from routeintel.integrations.company_data_base import CompanyDataSource
from routeintel.integrations.crm_base import CRMClient
from routeintel.schemas.lead import CompanyLeadView


class CRMSyncService:
    """Service for syncing trip data with CRM."""

    def __init__(
        self,
        db: Session,
        company_data_source: CompanyDataSource,
        crm_client: CRMClient,
    ) -> None:
        """Initialize service with dependencies."""
        self.discovery_service = CompanyDiscoveryService(db, company_data_source)
        self.matching_service = LeadMatchingService(db, crm_client)

    async def sync_leads_for_trip(
        self,
        trip_id: int,
        radius_km: float = 20.0,
    ) -> list[CompanyLeadView]:
        """Discover companies near trip and match to CRM.

        Args:
            trip_id: Trip identifier
            radius_km: Search radius in kilometers

        Returns:
            List of company-lead views with CRM status
        """
        companies = await self.discovery_service.find_companies_near_path(
            trip_id=trip_id,
            radius_km=radius_km,
        )

        lead_views = await self.matching_service.match_companies_to_crm(
            companies=companies,
        )

        return lead_views
