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
