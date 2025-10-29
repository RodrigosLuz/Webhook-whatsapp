# tests/conftest.py
import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app("dev")
    app.config.update(
        TESTING=True,
        DRY_RUN=True,
        PORT=5001,
    )
    yield app

@pytest.fixture
def client(app):
    return app.test_client()
