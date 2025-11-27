"""Mock company data source implementation.

Responsibility: Provide deterministic fake company data for demo/testing.
Dependencies: CompanyDataSource protocol, CompanyData schema
SOLID: Liskov Substitution - can be swapped with real data sources.
        Open/Closed - adding new data sources doesn't modify this code.
"""
import hashlib
from routeintel.schemas.company import CompanyData


class MockCompanyDataSource:
    """Mock company data source with deterministic fake companies."""

    def __init__(self) -> None:
        """Initialize mock data source with predefined companies."""
        self._base_companies = [
            {
                "name": "Acme Corporation",
                "industry": "Manufacturing",
                "employee_count": 250,
                "website": "acme.com",
            },
            {
                "name": "TechStart Inc",
                "industry": "Technology",
                "employee_count": 45,
                "website": "techstart.io",
            },
            {
                "name": "Global Manufacturing Ltd",
                "industry": "Manufacturing",
                "employee_count": 500,
                "website": "globalmanuf.com",
            },
            {
                "name": "Precision Parts Co",
                "industry": "Manufacturing",
                "employee_count": 120,
                "website": "precisionparts.com",
            },
            {
                "name": "Metro Supply Chain",
                "industry": "Logistics",
                "employee_count": 80,
                "website": "metrosupply.com",
            },
        ]

    async def get_companies_near(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[CompanyData]:
        """Get mock companies near a location.

        Uses lat/lon hash to deterministically select 2-4 companies,
        simulating proximity-based discovery.
        """
        location_hash = hashlib.md5(
            f"{latitude:.4f},{longitude:.4f}".encode()
        ).hexdigest()

        hash_value = int(location_hash[:8], 16)
        num_companies = 2 + (hash_value % 3)
        selected_indices = [(hash_value + i) % len(self._base_companies) for i in range(num_companies)]

        companies = []
        for idx in selected_indices:
            base = self._base_companies[idx]
            offset = (hash_value % 100) / 10000

            companies.append(
                CompanyData(
                    external_id=f"ext_{base['name'].lower().replace(' ', '_')}",
                    name=base["name"],
                    latitude=latitude + offset,
                    longitude=longitude + offset,
                    city="Birmingham",
                    state="AL",
                    country="USA",
                    industry=base["industry"],
                    employee_count=base["employee_count"],
                    website=base["website"],
                )
            )

        return companies


def get_company_data_source() -> MockCompanyDataSource:
    """Dependency injection factory for company data source."""
    return MockCompanyDataSource()
