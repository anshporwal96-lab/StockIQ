"""
tests/conftest.py
=================
Shared setup for the tests.

WHAT IS A FIXTURE?
------------------
A fixture is a piece of setup that pytest hands to any test that asks for it by
name. The `client` fixture below builds a fresh Flask app with a brand-new
temporary database, so tests never touch your real stockiq.db and never
interfere with each other.

RUN THE TESTS WITH:
    venv/Scripts/python -m pytest         (Windows)
    ./venv/bin/python -m pytest           (macOS / Linux)
"""

import os
import sys
import tempfile

import pytest

# Make sure the project folder is importable when pytest runs from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force demo data for the tests. They must never depend on a live API being up.
os.environ["DATA_PROVIDER"] = "demo"
os.environ["AI_API_KEY"] = ""            # exercise the rule-based fallback


@pytest.fixture()
def app():
    """A Flask app backed by a throwaway SQLite file."""
    from app import create_app
    from config import Config

    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + path.replace("\\", "/")
        SECRET_KEY = "test-secret-key"
        WTF_CSRF_ENABLED = False

    application = create_app(TestConfig)
    yield application

    # Clean up the temporary database afterwards.
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture()
def client(app):
    """A fake browser that can call our routes without a real network."""
    return app.test_client()


@pytest.fixture()
def csrf(client):
    """Fetch a CSRF token, which every POST and DELETE needs."""
    return client.get("/api/auth/csrf-token").get_json()["csrf_token"]


@pytest.fixture()
def logged_in(client, csrf):
    """Register a user and return headers carrying a valid CSRF token.

    Registering rotates the token (the session is cleared to prevent session
    fixation), so we return the NEW token, not the one we posted with.
    """
    response = client.post(
        "/api/auth/register",
        json={"username": "tester", "email": "tester@example.com", "password": "testpass123"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201
    return {"X-CSRF-Token": response.get_json()["csrf_token"]}
