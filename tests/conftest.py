import pytest

import storage
from app import create_app
from auth import set_user
from models import Base


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
        "UPLOAD_DIR": tmp_path / "fotos",
        "LOGIN_RATE_LIMIT": "5 per minute",
    })
    engine = storage.Session.get_bind()
    Base.metadata.create_all(engine)
    with app.app_context():
        set_user("schuetze", password="geheim1234")
    yield app
    storage.Session.remove()
    engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def eingeloggt(client):
    resp = client.post("/login", data={"name": "schuetze", "passwort": "geheim1234"})
    assert resp.status_code == 302
    return client


@pytest.fixture
def session(app):
    with app.app_context():
        yield storage.Session
