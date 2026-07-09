"""PUBLIC_BASE_PATH support — the app must serve identically at / (local dev)
and under a reverse-proxied prefix like boundstate.ai/hovor, where the proxy
forwards the prefix without stripping it."""

from fastapi.testclient import TestClient

from hovor.core.db import get_db
from hovor.main import create_app


def test_default_app_serves_at_root():
    client = TestClient(create_app(public_base_path=""))
    assert client.get("/health").status_code == 200
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/app/"


def test_prefixed_paths_are_stripped_and_served(db):
    app = create_app(public_base_path="/hovor")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        assert client.get("/hovor/health").status_code == 200
        assert client.get("/hovor/app/").status_code == 200
        users = client.post("/hovor/api/v1/users", json={"name": "Jozef"})
        assert users.status_code == 200


def test_prefix_root_redirects_inside_prefix():
    client = TestClient(create_app(public_base_path="/hovor"))
    root = client.get("/hovor", follow_redirects=False)
    assert root.status_code == 307
    assert root.headers["location"] == "/hovor/app/"


def test_unprefixed_paths_still_work_behind_prefix():
    # Railway health checks hit the bare service URL without the prefix.
    client = TestClient(create_app(public_base_path="/hovor"))
    assert client.get("/health").status_code == 200
