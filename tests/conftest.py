"""Shared test fixtures for Polaris DevTools."""

import pytest

from app import create_app
from models import db as _db


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app("testing")
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Database session."""
    with app.app_context():
        yield _db
