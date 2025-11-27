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
