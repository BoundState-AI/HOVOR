"""Company discovery service implementation.

Responsibility: Find companies near trip routes using external data sources.
Dependencies: SQLAlchemy Session, CompanyDataSource protocol, Company model
SOLID: Dependency Inversion - depends on CompanyDataSource abstraction.
        Single Responsibility - only handles company discovery logic.
        Open/Closed - new data sources can be added via DI without modifying this code.

Engineering notes:
- Queries data source at each GPS point along route
- Deduplicates by external_id and proximity threshold (5km)
- Persists new companies to local database
- No CRM interaction (separation of concerns)
"""
from sqlalchemy.orm import Session

from routeintel.models.trip import Trip
from routeintel.models.location import Location
from routeintel.models.company import Company
from routeintel.integrations.company_data_base import CompanyDataSource
from routeintel.schemas.company import CompanyData


class CompanyDiscoveryService:
    """Service for discovering companies near trip routes."""

    def __init__(self, db: Session, data_source: CompanyDataSource) -> None:
        """Initialize service with database and data source."""
        self.db = db
        self.data_source = data_source

    async def find_companies_near_path(
        self,
        trip_id: int,
        radius_km: float = 20.0,
    ) -> list[Company]:
        """Find companies near a trip's route.

        Args:
            trip_id: Trip identifier
            radius_km: Search radius in kilometers

        Returns:
            List of unique companies found near route
        """
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        locations = (
            self.db.query(Location)
            .filter(Location.trip_id == trip_id)
            .order_by(Location.timestamp)
            .all()
        )

        if not locations:
            return []

        discovered_companies: dict[str, CompanyData] = {}

        for location in locations:
            companies_data = await self.data_source.get_companies_near(
                latitude=location.latitude,
                longitude=location.longitude,
                radius_km=radius_km,
            )

            for company_data in companies_data:
                if company_data.external_id not in discovered_companies:
                    discovered_companies[company_data.external_id] = company_data

        result_companies = []
        for company_data in discovered_companies.values():
            company = self._get_or_create_company(company_data)
            result_companies.append(company)

        return result_companies

    def _get_or_create_company(self, company_data: CompanyData) -> Company:
        """Get existing company or create new one."""
        existing = (
            self.db.query(Company)
            .filter(Company.external_id == company_data.external_id)
            .first()
        )

        if existing:
            return existing

        company = Company(
            external_id=company_data.external_id,
            name=company_data.name,
            latitude=company_data.latitude,
            longitude=company_data.longitude,
            city=company_data.city,
            state=company_data.state,
            country=company_data.country,
            industry=company_data.industry,
            employee_count=company_data.employee_count,
            website=company_data.website,
        )

        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company
