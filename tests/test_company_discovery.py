"""Test company discovery service."""
import pytest
from sqlalchemy.orm import Session

from routeintel.services.trip_service import TripService
from routeintel.services.company_discovery_service import CompanyDiscoveryService
from routeintel.integrations.company_data_mock import MockCompanyDataSource
from routeintel.schemas.trip import TripCreate
from routeintel.schemas.location import LocationCreate


@pytest.mark.asyncio
async def test_find_companies_near_path(db_session: Session):
    """Test discovering companies near a trip path."""
    trip_service = TripService(db_session)
    data_source = MockCompanyDataSource()
    discovery_service = CompanyDiscoveryService(db_session, data_source)

    trip = trip_service.start_trip(TripCreate(user_id="user123"))

    locations = [
        LocationCreate(latitude=33.5186, longitude=-86.8104),
        LocationCreate(latitude=33.5286, longitude=-86.8204),
    ]

    for location in locations:
        trip_service.append_location(trip.id, location)

    companies = await discovery_service.find_companies_near_path(trip.id, radius_km=20.0)

    assert len(companies) > 0
    assert all(company.name for company in companies)
    assert all(company.external_id for company in companies)


@pytest.mark.asyncio
async def test_company_deduplication(db_session: Session):
    """Test that companies are deduplicated by external_id."""
    trip_service = TripService(db_session)
    data_source = MockCompanyDataSource()
    discovery_service = CompanyDiscoveryService(db_session, data_source)

    trip = trip_service.start_trip(TripCreate(user_id="user123"))

    locations = [
        LocationCreate(latitude=33.5186, longitude=-86.8104),
        LocationCreate(latitude=33.5186, longitude=-86.8104),
    ]

    for location in locations:
        trip_service.append_location(trip.id, location)

    companies = await discovery_service.find_companies_near_path(trip.id, radius_km=20.0)

    external_ids = [c.external_id for c in companies]
    assert len(external_ids) == len(set(external_ids))


@pytest.mark.asyncio
async def test_company_persistence(db_session: Session):
    """Test that companies are persisted to database."""
    trip_service = TripService(db_session)
    data_source = MockCompanyDataSource()
    discovery_service = CompanyDiscoveryService(db_session, data_source)

    trip = trip_service.start_trip(TripCreate(user_id="user123"))
    trip_service.append_location(trip.id, LocationCreate(latitude=33.5186, longitude=-86.8104))

    companies_first = await discovery_service.find_companies_near_path(trip.id, radius_km=20.0)
    companies_second = await discovery_service.find_companies_near_path(trip.id, radius_km=20.0)

    assert len(companies_first) == len(companies_second)
    assert companies_first[0].id == companies_second[0].id
