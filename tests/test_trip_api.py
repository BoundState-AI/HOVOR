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
