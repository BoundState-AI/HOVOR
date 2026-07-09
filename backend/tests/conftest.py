import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import hovor.core.db as core_db
from hovor.content.loader import load_content
from hovor.core.db import Base, get_db
from hovor.main import create_app


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # Keep app startup from touching a real database file.
    monkeypatch.setattr(core_db, "engine", engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture()
def content():
    return load_content()


@pytest.fixture()
def client(db):
    app = create_app()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
