"""Test lead matching service."""
import pytest
from sqlalchemy.orm import Session

from routeintel.services.lead_matching_service import LeadMatchingService
from routeintel.integrations.crm_pipedrive import PipedriveCRMClient
from routeintel.models.company import Company
from routeintel.models.lead import LeadStatus


@pytest.mark.asyncio
async def test_match_existing_customer(db_session: Session):
    """Test matching a company that exists in CRM as customer."""
    crm_client = PipedriveCRMClient()
    matching_service = LeadMatchingService(db_session, crm_client)

    company = Company(
        external_id="ext_test_1",
        name="Acme Corporation",
        latitude=33.5186,
        longitude=-86.8104,
        website="acme.com",
    )
    db_session.add(company)
    db_session.commit()

    lead_views = await matching_service.match_companies_to_crm([company])

    assert len(lead_views) == 1
    assert lead_views[0].lead_status == LeadStatus.CUSTOMER
    assert lead_views[0].crm_id is not None


@pytest.mark.asyncio
async def test_match_new_company(db_session: Session):
    """Test matching a company that doesn't exist in CRM."""
    crm_client = PipedriveCRMClient()
    matching_service = LeadMatchingService(db_session, crm_client)

    company = Company(
        external_id="ext_new_company",
        name="Brand New Company",
        latitude=33.5186,
        longitude=-86.8104,
        website="newcompany.com",
    )
    db_session.add(company)
    db_session.commit()

    lead_views = await matching_service.match_companies_to_crm([company])

    assert len(lead_views) == 1
    assert lead_views[0].lead_status == LeadStatus.NEW
    assert lead_views[0].crm_id is None


@pytest.mark.asyncio
async def test_match_by_domain_and_name(db_session: Session):
    """Test that matching tries domain first, then name."""
    crm_client = PipedriveCRMClient()
    matching_service = LeadMatchingService(db_session, crm_client)

    company_with_domain = Company(
        external_id="ext_test_2",
        name="TechStart Inc",
        latitude=33.5186,
        longitude=-86.8104,
        website="techstart.io",
    )

    company_no_domain = Company(
        external_id="ext_test_3",
        name="Global Manufacturing Ltd",
        latitude=33.5286,
        longitude=-86.8204,
    )

    db_session.add(company_with_domain)
    db_session.add(company_no_domain)
    db_session.commit()

    lead_views = await matching_service.match_companies_to_crm(
        [company_with_domain, company_no_domain]
    )

    assert len(lead_views) == 2
    assert all(view.lead_status in [LeadStatus.CUSTOMER, LeadStatus.PROSPECT] for view in lead_views)
