# RouteIntel MVP - Complete Code

## Project Overview

Route-aware sales travel intelligence application built with FastAPI, SQLAlchemy, and SOLID architecture.

## Installation & Quick Start

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -e ".[dev]"

# Run application
uv run uvicorn routeintel.main:app --reload

# Run tests
uv run pytest tests/ -v
```

Access:
- Dashboard: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## File: pyproject.toml

```toml
[project]
name = "routeintel"
version = "0.1.0"
description = "Route-aware sales travel intelligence app"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "python-multipart>=0.0.6",
    "jinja2>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.26.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## File: .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
.venv/
venv/
ENV/
env/

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/

# Package management
uv.lock
*.egg-info/
dist/
build/

# OS
.DS_Store
Thumbs.db
```

---

## File: routeintel/__init__.py

```python
```

---

## File: routeintel/main.py

```python
"""RouteIntel FastAPI application.

Main application entry point with route registration and web UI.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from routeintel.core.config import get_settings
from routeintel.core.db import init_db
from routeintel.core.logging import setup_logging
from routeintel.api.routes_trips import router as trips_router
from routeintel.api.routes_companies import router as companies_router

settings = get_settings()
setup_logging()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

init_db()

app.mount("/static", StaticFiles(directory="routeintel/web/static"), name="static")
templates = Jinja2Templates(directory="routeintel/web/templates")

app.include_router(trips_router, prefix=settings.api_v1_prefix)
app.include_router(companies_router, prefix=settings.api_v1_prefix)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
```

---

## File: routeintel/core/__init__.py

```python
```

---

## File: routeintel/core/config.py

```python
"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "sqlite:///./routeintel.db"

    # API
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    # App
    app_name: str = "RouteIntel"
    app_version: str = "0.1.0"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
```

---

## File: routeintel/core/db.py

```python
"""Database session management."""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from routeintel.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
```

---

## File: routeintel/core/logging.py

```python
"""Logging configuration."""
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
```

---

## File: routeintel/models/__init__.py

```python
```

---

## File: routeintel/models/trip.py

```python
"""Trip database model.

Responsibility: Represents a single driving route/segment.
Dependencies: SQLAlchemy Base from core.db
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class TripStatus(str, PyEnum):
    """Trip status enum."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class Trip(Base):
    """Trip model representing a single route segment."""

    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    status = Column(Enum(TripStatus), nullable=False, default=TripStatus.ACTIVE)
    total_distance_km = Column(Float, nullable=False, default=0.0)
    purpose = Column(String, nullable=True)

    # Relationships
    locations = relationship("Location", back_populates="trip", cascade="all, delete-orphan")
```

---

## File: routeintel/models/location.py

```python
"""Location database model.

Responsibility: GPS breadcrumb tied to a trip.
Dependencies: SQLAlchemy Base, Trip model
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class Location(Base):
    """Location model representing GPS coordinates for a trip."""

    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, nullable=True)
    is_stop = Column(Boolean, nullable=False, default=False)

    # Relationships
    trip = relationship("Trip", back_populates="locations")
```

---

## File: routeintel/models/company.py

```python
"""Company database model.

Responsibility: Nearby business that might be a lead.
Dependencies: SQLAlchemy Base
"""
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class Company(Base):
    """Company model representing a potential lead."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, nullable=True, unique=True, index=True)
    name = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    employee_count = Column(Integer, nullable=True)
    website = Column(String, nullable=True)

    # Relationships
    leads = relationship("Lead", back_populates="company", cascade="all, delete-orphan")
```

---

## File: routeintel/models/lead.py

```python
"""Lead database model.

Responsibility: Relationship between user and a company.
Dependencies: SQLAlchemy Base, Company model
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship

from routeintel.core.db import Base


class LeadStatus(str, PyEnum):
    """Lead status enum."""

    CUSTOMER = "CUSTOMER"
    PROSPECT = "PROSPECT"
    NEW = "NEW"


class Lead(Base):
    """Lead model representing the relationship between user and company."""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    crm_id = Column(String, nullable=True, unique=True, index=True)
    status = Column(Enum(LeadStatus), nullable=False, default=LeadStatus.NEW)
    last_contacted_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="leads")
```

---

## File: routeintel/schemas/__init__.py

```python
```

---

## File: routeintel/schemas/trip.py

```python
"""Trip Pydantic schemas.

Responsibility: API request/response models for Trip.
Dependencies: Pydantic, TripStatus enum
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from routeintel.models.trip import TripStatus


class TripBase(BaseModel):
    """Base trip schema."""

    user_id: str
    purpose: str | None = None


class TripCreate(TripBase):
    """Schema for creating a trip."""

    pass


class TripUpdate(BaseModel):
    """Schema for updating a trip."""

    purpose: str | None = None
    status: TripStatus | None = None


class TripRead(TripBase):
    """Schema for reading a trip."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    ended_at: datetime | None
    status: TripStatus
    total_distance_km: float
```

---

## File: routeintel/schemas/location.py

```python
"""Location Pydantic schemas.

Responsibility: API request/response models for Location.
Dependencies: Pydantic
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LocationBase(BaseModel):
    """Base location schema."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: float | None = Field(None, ge=0)


class LocationCreate(LocationBase):
    """Schema for creating a location."""

    timestamp: datetime | None = None


class LocationRead(LocationBase):
    """Schema for reading a location."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    timestamp: datetime
    is_stop: bool
```

---

## File: routeintel/schemas/company.py

```python
"""Company Pydantic schemas.

Responsibility: API request/response models for Company.
Dependencies: Pydantic
"""
from pydantic import BaseModel, ConfigDict, Field


class CompanyBase(BaseModel):
    """Base company schema."""

    name: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    city: str | None = None
    state: str | None = None
    country: str | None = None
    industry: str | None = None
    employee_count: int | None = Field(None, ge=0)
    website: str | None = None


class CompanyCreate(CompanyBase):
    """Schema for creating a company."""

    external_id: str | None = None


class CompanyRead(CompanyBase):
    """Schema for reading a company."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None


class CompanyData(BaseModel):
    """Schema for company data from external sources."""

    external_id: str
    name: str
    latitude: float
    longitude: float
    city: str | None = None
    state: str | None = None
    country: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    website: str | None = None
```

---

## File: routeintel/schemas/lead.py

```python
"""Lead Pydantic schemas.

Responsibility: API request/response models for Lead.
Dependencies: Pydantic, LeadStatus enum, CompanyRead schema
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from routeintel.models.lead import LeadStatus
from routeintel.schemas.company import CompanyRead


class LeadBase(BaseModel):
    """Base lead schema."""

    status: LeadStatus
    notes: str | None = None


class LeadCreate(LeadBase):
    """Schema for creating a lead."""

    company_id: int
    crm_id: str | None = None
    last_contacted_at: datetime | None = None


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""

    status: LeadStatus | None = None
    crm_id: str | None = None
    last_contacted_at: datetime | None = None
    notes: str | None = None


class LeadRead(LeadBase):
    """Schema for reading a lead."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    crm_id: str | None
    last_contacted_at: datetime | None


class CompanyLeadView(BaseModel):
    """Combined view of company and lead status."""

    company: CompanyRead
    lead_status: LeadStatus
    last_contacted_at: datetime | None
    crm_id: str | None
```

---

## File: routeintel/services/__init__.py

```python
```

---

## File: routeintel/services/trip_service.py

```python
"""Trip service implementation.

Responsibility: Manage trip lifecycle and location tracking.
Dependencies: SQLAlchemy Session, Trip/Location models, schemas
SOLID: Single Responsibility - only handles trip business logic.
        Dependency Inversion - depends on DB session abstraction.

Engineering notes:
- Uses haversine formula for distance calculation
- Computes total distance from ordered GPS breadcrumbs
- No external service dependencies
"""
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
from sqlalchemy.orm import Session

from routeintel.models.trip import Trip, TripStatus
from routeintel.models.location import Location
from routeintel.schemas.trip import TripCreate
from routeintel.schemas.location import LocationCreate


class TripService:
    """Service for trip operations."""

    def __init__(self, db: Session) -> None:
        """Initialize service with database session."""
        self.db = db

    def start_trip(self, trip_data: TripCreate) -> Trip:
        """Start a new trip."""
        trip = Trip(
            user_id=trip_data.user_id,
            purpose=trip_data.purpose,
            status=TripStatus.ACTIVE,
            started_at=datetime.utcnow(),
        )
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def end_trip(self, trip_id: int) -> Trip:
        """End an active trip and compute final distance."""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        trip.ended_at = datetime.utcnow()
        trip.status = TripStatus.COMPLETED
        trip.total_distance_km = self.compute_total_distance(trip_id)

        self.db.commit()
        self.db.refresh(trip)
        return trip

    def append_location(self, trip_id: int, location_data: LocationCreate) -> Location:
        """Append a GPS location to a trip."""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        location = Location(
            trip_id=trip_id,
            latitude=location_data.latitude,
            longitude=location_data.longitude,
            speed_kmh=location_data.speed_kmh,
            timestamp=location_data.timestamp or datetime.utcnow(),
        )

        self.db.add(location)
        self.db.commit()
        self.db.refresh(location)
        return location

    def compute_total_distance(self, trip_id: int) -> float:
        """Compute total distance for a trip using haversine formula."""
        locations = (
            self.db.query(Location)
            .filter(Location.trip_id == trip_id)
            .order_by(Location.timestamp)
            .all()
        )

        if len(locations) < 2:
            return 0.0

        total_km = 0.0
        for i in range(len(locations) - 1):
            loc1 = locations[i]
            loc2 = locations[i + 1]
            total_km += self._haversine_distance(
                loc1.latitude, loc1.longitude, loc2.latitude, loc2.longitude
            )

        return round(total_km, 2)

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using haversine formula.

        Returns distance in kilometers.
        """
        R = 6371  # Earth radius in kilometers

        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        return R * c
```

---

## File: routeintel/services/company_discovery_service.py

```python
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
```

---

## File: routeintel/services/lead_matching_service.py

```python
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
```

---

## File: routeintel/services/crm_sync_service.py

```python
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
```

---

## File: routeintel/integrations/__init__.py

```python
```

---

## File: routeintel/integrations/crm_base.py

```python
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
```

---

## File: routeintel/integrations/crm_pipedrive.py

```python
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
```

---

## File: routeintel/integrations/company_data_base.py

```python
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
```

---

## File: routeintel/integrations/company_data_mock.py

```python
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
```

---

## File: routeintel/api/__init__.py

```python
```

---

## File: routeintel/api/routes_trips.py

```python
"""Trip API routes.

Responsibility: Handle HTTP requests for trip operations.
Dependencies: FastAPI, TripService, DB session
SOLID: Single Responsibility - only handles HTTP layer for trips.
        Dependency Inversion - delegates to TripService abstraction.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from routeintel.core.db import get_db
from routeintel.services.trip_service import TripService
from routeintel.schemas.trip import TripCreate, TripRead
from routeintel.schemas.location import LocationCreate, LocationRead

router = APIRouter(prefix="/trips", tags=["trips"])


def get_trip_service(db: Session = Depends(get_db)) -> TripService:
    """Dependency injection for TripService."""
    return TripService(db)


@router.post("/start", response_model=TripRead)
def start_trip(
    trip_data: TripCreate,
    service: TripService = Depends(get_trip_service),
) -> TripRead:
    """Start a new trip."""
    trip = service.start_trip(trip_data)
    return TripRead.model_validate(trip)


@router.post("/{trip_id}/end", response_model=TripRead)
def end_trip(
    trip_id: int,
    service: TripService = Depends(get_trip_service),
) -> TripRead:
    """End a trip and compute final distance."""
    try:
        trip = service.end_trip(trip_id)
        return TripRead.model_validate(trip)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{trip_id}/locations", response_model=LocationRead)
def add_location(
    trip_id: int,
    location_data: LocationCreate,
    service: TripService = Depends(get_trip_service),
) -> LocationRead:
    """Add a GPS location to a trip."""
    try:
        location = service.append_location(trip_id, location_data)
        return LocationRead.model_validate(location)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
) -> TripRead:
    """Get trip details."""
    from routeintel.models.trip import Trip

    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")
    return TripRead.model_validate(trip)


@router.get("", response_model=list[TripRead])
def list_trips(
    user_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[TripRead]:
    """List trips, optionally filtered by user_id."""
    from routeintel.models.trip import Trip

    query = db.query(Trip)
    if user_id:
        query = query.filter(Trip.user_id == user_id)

    trips = query.all()
    return [TripRead.model_validate(trip) for trip in trips]
```

---

## File: routeintel/api/routes_companies.py

```python
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
```

---

## File: routeintel/web/__init__.py

```python
```

---

## File: routeintel/web/templates/base.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}RouteIntel{% endblock %}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 30px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
        }
        .error {
            background: #fee;
            border: 1px solid #fcc;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .info {
            background: #e3f2fd;
            border: 1px solid #90caf9;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
    </style>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
```

---

## File: routeintel/web/templates/dashboard.html

```html
{% extends "base.html" %}

{% block title %}RouteIntel Dashboard{% endblock %}

{% block extra_head %}
<style>
    .controls {
        margin-bottom: 30px;
        padding: 20px;
        background: #f8f9fa;
        border-radius: 4px;
    }
    select, input, button {
        padding: 8px 12px;
        margin: 5px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-size: 14px;
    }
    button {
        background: #3498db;
        color: white;
        border: none;
        cursor: pointer;
    }
    button:hover {
        background: #2980b9;
    }
    button:disabled {
        background: #95a5a6;
        cursor: not-allowed;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }
    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid #ddd;
    }
    th {
        background: #34495e;
        color: white;
        font-weight: 600;
    }
    tr:hover {
        background: #f5f5f5;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    }
    .status-customer {
        background: #2ecc71;
        color: white;
    }
    .status-prospect {
        background: #f39c12;
        color: white;
    }
    .status-new {
        background: #95a5a6;
        color: white;
    }
    .trip-info {
        background: #ecf0f1;
        padding: 15px;
        border-radius: 4px;
        margin-bottom: 20px;
    }
    .loading {
        text-align: center;
        padding: 40px;
        color: #7f8c8d;
    }
</style>
{% endblock %}

{% block content %}
<h1>RouteIntel Dashboard</h1>

<div class="controls">
    <h2>Trip Selection</h2>
    <select id="tripSelect">
        <option value="">Select a trip...</option>
    </select>
    <input type="number" id="radiusInput" placeholder="Radius (km)" value="20" min="1" max="100">
    <button id="loadButton" disabled>Load Leads</button>
</div>

<div id="tripInfo" style="display: none;"></div>
<div id="resultsContainer"></div>

<script src="/static/app.js"></script>
{% endblock %}
```

---

## File: routeintel/web/static/app.js

```javascript
const API_BASE = '/api/v1';

const tripSelect = document.getElementById('tripSelect');
const radiusInput = document.getElementById('radiusInput');
const loadButton = document.getElementById('loadButton');
const tripInfo = document.getElementById('tripInfo');
const resultsContainer = document.getElementById('resultsContainer');

async function fetchTrips() {
    try {
        const response = await fetch(`${API_BASE}/trips`);
        const trips = await response.json();

        tripSelect.innerHTML = '<option value="">Select a trip...</option>';

        trips.forEach(trip => {
            const option = document.createElement('option');
            option.value = trip.id;
            const date = new Date(trip.started_at).toLocaleDateString();
            const purpose = trip.purpose || 'No purpose';
            option.textContent = `Trip #${trip.id} - ${date} - ${purpose}`;
            tripSelect.appendChild(option);
        });
    } catch (error) {
        showError('Failed to load trips: ' + error.message);
    }
}

async function loadTripLeads() {
    const tripId = tripSelect.value;
    const radius = radiusInput.value || 20;

    if (!tripId) return;

    loadButton.disabled = true;
    resultsContainer.innerHTML = '<div class="loading">Loading lead data...</div>';

    try {
        const [tripResponse, leadsResponse] = await Promise.all([
            fetch(`${API_BASE}/trips/${tripId}`),
            fetch(`${API_BASE}/trips/${tripId}/lead_view?radius_km=${radius}`)
        ]);

        const trip = await tripResponse.json();
        const leads = await leadsResponse.json();

        displayTripInfo(trip);
        displayLeads(leads);
    } catch (error) {
        showError('Failed to load lead data: ' + error.message);
    } finally {
        loadButton.disabled = false;
    }
}

function displayTripInfo(trip) {
    const startDate = new Date(trip.started_at).toLocaleString();
    const endDate = trip.ended_at ? new Date(trip.ended_at).toLocaleString() : 'In Progress';

    tripInfo.style.display = 'block';
    tripInfo.innerHTML = `
        <div class="trip-info">
            <h2>Trip Summary</h2>
            <p><strong>Trip ID:</strong> ${trip.id}</p>
            <p><strong>User:</strong> ${trip.user_id}</p>
            <p><strong>Purpose:</strong> ${trip.purpose || 'N/A'}</p>
            <p><strong>Started:</strong> ${startDate}</p>
            <p><strong>Ended:</strong> ${endDate}</p>
            <p><strong>Status:</strong> ${trip.status}</p>
            <p><strong>Distance:</strong> ${trip.total_distance_km.toFixed(2)} km</p>
        </div>
    `;
}

function displayLeads(leads) {
    if (leads.length === 0) {
        resultsContainer.innerHTML = '<div class="info">No companies found near this route.</div>';
        return;
    }

    let html = `
        <h2>Nearby Companies (${leads.length} found)</h2>
        <table>
            <thead>
                <tr>
                    <th>Company Name</th>
                    <th>City/State</th>
                    <th>Industry</th>
                    <th>Employees</th>
                    <th>Status</th>
                    <th>Last Contact</th>
                </tr>
            </thead>
            <tbody>
    `;

    leads.forEach(lead => {
        const company = lead.company;
        const location = [company.city, company.state].filter(x => x).join(', ') || 'N/A';
        const lastContact = lead.last_contacted_at
            ? new Date(lead.last_contacted_at).toLocaleDateString()
            : 'Never';
        const statusClass = `status-${lead.lead_status.toLowerCase()}`;

        html += `
            <tr>
                <td><strong>${company.name}</strong></td>
                <td>${location}</td>
                <td>${company.industry || 'N/A'}</td>
                <td>${company.employee_count || 'N/A'}</td>
                <td><span class="status-badge ${statusClass}">${lead.lead_status}</span></td>
                <td>${lastContact}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    resultsContainer.innerHTML = html;
}

function showError(message) {
    resultsContainer.innerHTML = `<div class="error">${message}</div>`;
}

tripSelect.addEventListener('change', () => {
    loadButton.disabled = !tripSelect.value;
    tripInfo.style.display = 'none';
    resultsContainer.innerHTML = '';
});

loadButton.addEventListener('click', loadTripLeads);

fetchTrips();
```

---

## File: tests/__init__.py

```python
```

---

## File: tests/conftest.py

```python
"""Pytest configuration and fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from routeintel.core.db import Base, get_db
from routeintel.main import app


@pytest.fixture
def db_session() -> Session:
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a test client with dependency overrides."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
```

---

## File: tests/test_trip_api.py

```python
"""Test trip API endpoints."""
import pytest
from fastapi.testclient import TestClient


def test_start_trip(client: TestClient):
    """Test starting a new trip."""
    response = client.post(
        "/api/v1/trips/start",
        json={"user_id": "user123", "purpose": "Sales trip - Birmingham"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == "user123"
    assert data["purpose"] == "Sales trip - Birmingham"
    assert data["status"] == "ACTIVE"
    assert data["total_distance_km"] == 0.0


def test_end_trip(client: TestClient):
    """Test ending a trip."""
    start_response = client.post(
        "/api/v1/trips/start",
        json={"user_id": "user123"},
    )
    trip_id = start_response.json()["id"]

    end_response = client.post(f"/api/v1/trips/{trip_id}/end")
    assert end_response.status_code == 200
    data = end_response.json()
    assert data["status"] == "COMPLETED"
    assert data["ended_at"] is not None


def test_append_locations_and_compute_distance(client: TestClient):
    """Test appending GPS locations and distance calculation."""
    start_response = client.post(
        "/api/v1/trips/start",
        json={"user_id": "user123"},
    )
    trip_id = start_response.json()["id"]

    locations = [
        {"latitude": 33.5186, "longitude": -86.8104},
        {"latitude": 33.5286, "longitude": -86.8204},
        {"latitude": 33.5386, "longitude": -86.8304},
    ]

    for location in locations:
        response = client.post(
            f"/api/v1/trips/{trip_id}/locations",
            json=location,
        )
        assert response.status_code == 200

    end_response = client.post(f"/api/v1/trips/{trip_id}/end")
    data = end_response.json()
    assert data["total_distance_km"] > 0


def test_get_trip(client: TestClient):
    """Test getting trip details."""
    start_response = client.post(
        "/api/v1/trips/start",
        json={"user_id": "user123"},
    )
    trip_id = start_response.json()["id"]

    get_response = client.get(f"/api/v1/trips/{trip_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == trip_id


def test_list_trips(client: TestClient):
    """Test listing trips."""
    client.post("/api/v1/trips/start", json={"user_id": "user123"})
    client.post("/api/v1/trips/start", json={"user_id": "user456"})

    response = client.get("/api/v1/trips")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/api/v1/trips?user_id=user123")
    assert response.status_code == 200
    assert len(response.json()) == 1
```

---

## File: tests/test_company_discovery.py

```python
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
```

---

## File: tests/test_lead_matching.py

```python
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
```

---

## README

# RouteIntel MVP

Route-aware sales travel intelligence application. Turn normal car travel + expense tracking into a sales-intelligence workflow.

## Features

- Track trips and mileage automatically via GPS coordinates
- Discover companies within X miles of the route
- Match companies to CRM (customers, prospects, new leads)
- Clean REST API with FastAPI
- Minimal web UI dashboard
- SOLID architecture with dependency injection
- Mock implementations for CRM and company data sources

## Tech Stack

- **Backend**: Python 3.11+, FastAPI
- **Data**: SQLAlchemy + SQLite
- **Tests**: pytest
- **Package Manager**: uv

## Project Structure

```
routeintel/
├── core/              # Configuration, DB, logging
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic schemas
├── services/          # Business logic (SOLID)
├── integrations/      # External service abstractions + mocks
├── api/               # FastAPI routes
├── web/               # Templates and static files
└── main.py            # Application entry point
tests/                 # pytest tests
```

## Quick Start

### Installation

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -e ".[dev]"
```

### Run Application

```bash
uv run uvicorn routeintel.main:app --reload
```

The application will be available at:
- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Run Tests

```bash
uv run pytest tests/ -v
```

## API Usage Examples

### 1. Start a Trip

```bash
curl -X POST http://localhost:8000/api/v1/trips/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123", "purpose": "Sales trip - Birmingham"}'
```

### 2. Add GPS Locations

```bash
curl -X POST http://localhost:8000/api/v1/trips/1/locations \
  -H "Content-Type: application/json" \
  -d '{"latitude": 33.5186, "longitude": -86.8104}'
```

### 3. End Trip

```bash
curl -X POST http://localhost:8000/api/v1/trips/1/end
```

### 4. Get Companies Near Route

```bash
curl http://localhost:8000/api/v1/trips/1/nearby_companies?radius_km=20
```

### 5. Get Lead View (Companies + CRM Status)

```bash
curl http://localhost:8000/api/v1/trips/1/lead_view?radius_km=20
```

## Architecture

### SOLID Principles

- **Single Responsibility**: Each service handles one aspect of business logic
- **Open/Closed**: Abstract interfaces allow new integrations without modifying core code
- **Liskov Substitution**: Mock and real implementations are interchangeable
- **Interface Segregation**: Minimal, focused interfaces (CRMClient, CompanyDataSource)
- **Dependency Inversion**: Services depend on abstractions, not concrete implementations

### Service Layer

- **TripService**: Trip lifecycle management, location tracking, distance calculation
- **CompanyDiscoveryService**: Find companies near routes using data sources
- **LeadMatchingService**: Match companies to CRM records
- **CRMSyncService**: Orchestrate discovery and matching

### Integration Layer

- **CRMClient** (Protocol): Abstract CRM interface
- **PipedriveCRMClient**: Mock CRM implementation
- **CompanyDataSource** (Protocol): Abstract company data interface
- **MockCompanyDataSource**: Deterministic fake company data

## Next Steps

To integrate real data sources:

1. Implement `CompanyDataSource` for:
   - Google Places API
   - LinkedIn Sales Navigator API
   - Chamber of Commerce data
   - Trade magazine databases

2. Implement `CRMClient` for:
   - Real Pipedrive integration
   - Salesforce
   - HubSpot

3. Add authentication and user management

4. Build mobile app that consumes these APIs

## License

Proprietary - BoundState AI
