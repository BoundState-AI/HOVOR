"""Company and lead API routes.

Responsibility: Handle HTTP requests for company discovery and lead matching.
Dependencies: FastAPI, CRMSyncService, CompanyDiscoveryService, DB session
SOLID: Single Responsibility - only handles HTTP layer for companies/leads.
        Dependency Inversion - delegates to service abstractions.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from routeintel.core.db import get_db
from routeintel.services.crm_sync_service import CRMSyncService
from routeintel.services.company_discovery_service import CompanyDiscoveryService
from routeintel.integrations.crm_pipedrive import get_crm_client
from routeintel.integrations.company_data_mock import get_company_data_source
from routeintel.integrations.crm_base import CRMClient
from routeintel.integrations.company_data_base import CompanyDataSource
from routeintel.schemas.company import CompanyRead
from routeintel.schemas.lead import CompanyLeadView

router = APIRouter(prefix="/trips", tags=["companies", "leads"])


def get_discovery_service(
    db: Session = Depends(get_db),
    data_source: CompanyDataSource = Depends(get_company_data_source),
) -> CompanyDiscoveryService:
    """Dependency injection for CompanyDiscoveryService."""
    return CompanyDiscoveryService(db, data_source)


def get_crm_sync_service(
    db: Session = Depends(get_db),
    data_source: CompanyDataSource = Depends(get_company_data_source),
    crm_client: CRMClient = Depends(get_crm_client),
) -> CRMSyncService:
    """Dependency injection for CRMSyncService."""
    return CRMSyncService(db, data_source, crm_client)


@router.get("/{trip_id}/nearby_companies", response_model=list[CompanyRead])
async def get_nearby_companies(
    trip_id: int,
    radius_km: float = 20.0,
    service: CompanyDiscoveryService = Depends(get_discovery_service),
) -> list[CompanyRead]:
    """Get companies near a trip's route."""
    companies = await service.find_companies_near_path(trip_id, radius_km)
    return [CompanyRead.model_validate(company) for company in companies]


@router.get("/{trip_id}/lead_view", response_model=list[CompanyLeadView])
async def get_lead_view(
    trip_id: int,
    radius_km: float = 20.0,
    service: CRMSyncService = Depends(get_crm_sync_service),
) -> list[CompanyLeadView]:
    """Get companies near trip with CRM lead status."""
    return await service.sync_leads_for_trip(trip_id, radius_km)
