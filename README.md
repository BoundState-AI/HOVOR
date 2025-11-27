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
