import pytest
from fastapi.testclient import TestClient
from jarvis.api import create_app
from jarvis.calendar import CalendarService
from jarvis.config import Settings
from jarvis.db import Database

TOKEN = "test-token-with-at-least-32-characters"


@pytest.fixture
def settings(tmp_path):
    config = Settings(data_dir=tmp_path, token=TOKEN, mcp_transport="inprocess", _env_file=None)
    config.prepare()
    return config


@pytest.fixture
def db(settings):
    database = Database(settings)
    database.initialize()
    yield database
    database.engine.dispose()


@pytest.fixture
def service(db):
    return CalendarService(db)


@pytest.fixture
def client(settings, db):
    with TestClient(create_app(settings, db)) as c:
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        yield c


@pytest.fixture
def event_data():
    return {
        "calendar_id": "personal",
        "title": "Dinner with Sam",
        "start": "2026-10-21T19:00:00+08:00",
        "duration_minutes": 60,
        "timezone": "Asia/Singapore",
        "location": "Home",
        "duration_is_estimate": True,
    }


@pytest.fixture
def create_event(service, event_data):
    def create(**changes):
        p = service.propose("event_create", {**event_data, **changes})
        service.approve(p["id"])
        return service.execute_local(p["id"])

    return create
