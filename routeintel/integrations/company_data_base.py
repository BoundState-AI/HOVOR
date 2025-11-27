"""Company data source abstract interface.

Responsibility: Define contract for company data providers.
Dependencies: Protocol, CompanyData schema
SOLID: Interface Segregation - single method focused on location-based search.
        Open/Closed - new data sources can be added without modifying existing code.
"""
from typing import Protocol

from routeintel.schemas.company import CompanyData


class CompanyDataSource(Protocol):
    """Abstract interface for company data sources."""

    async def get_companies_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[CompanyData]:
        """Get companies near a geographic point."""
        ...
