import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Configure SQLite for test runs
os.environ["DATABASE_URL"] = "sqlite:///./test_parking.db"
os.environ["SECRET_KEY"] = "test-secret-key-123456"

backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.db.base import Base
from app.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    db_file = Path("./test_parking.db")
    if db_file.exists():
        db_file.unlink()


client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_auth_login_admin():
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "Admin@123456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "admin"


def test_list_zones():
    response = client.get("/api/v1/zones")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_violations():
    response = client.get("/api/v1/violations")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "meta" in data


def test_dashboard_stats():
    response = client.get("/api/v1/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_violations" in data
    assert "by_label" in data
