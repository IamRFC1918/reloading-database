import re
from urllib.parse import urlparse

import pytest

from auth import authenticate, set_user


def test_ohne_login_umleitung(client):
    resp = client.get("/")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


@pytest.mark.parametrize("pfad", ["/laborierung/neu", "/lose", "/backup", "/backup/export.json", "/fotos/x.jpg"])
def test_alle_seiten_geschuetzt(client, pfad):
    assert client.get(pfad).status_code == 302


def test_healthz_und_login_oeffentlich(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/login").status_code == 200


def test_login_erfolgreich(client):
    resp = client.post("/login", data={"name": "schuetze", "passwort": "geheim1234"})
    assert resp.status_code == 302
    assert client.get("/").status_code == 200


def test_login_falsches_passwort(client):
    resp = client.post("/login", data={"name": "schuetze", "passwort": "falsch"})
    assert resp.status_code == 200
    assert "falsch" in resp.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_kein_open_redirect(client):
    resp = client.post("/login?next=//boese.example", data={"name": "schuetze", "passwort": "geheim1234"})
    assert resp.headers["Location"] == "/"


def test_session_cookie_flags(app):
    app.config["SESSION_COOKIE_SECURE"] = True
    client = app.test_client()
    resp = client.post("/login", data={"name": "schuetze", "passwort": "geheim1234"})
    cookie = resp.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie


def test_rate_limit_am_login(client):
    for _ in range(5):
        client.post("/login", data={"name": "schuetze", "passwort": "falsch"})
    assert client.post("/login", data={"name": "schuetze", "passwort": "falsch"}).status_code == 429


def test_logout(eingeloggt):
    eingeloggt.post("/logout")
    assert eingeloggt.get("/").status_code == 302


def test_passwort_hash_argon2(session):
    user = set_user("zweiter", password="noch-ein-passwort")
    assert user.passwort_hash.startswith("$argon2id$")
    assert authenticate("zweiter", "noch-ein-passwort").id == user.id
    assert authenticate("zweiter", "falsch") is None
    assert authenticate("unbekannt", "egal") is None


def test_set_user_mit_hash_aus_secret(session):
    from auth import hasher
    h = hasher.hash("aus-dem-secret")
    set_user("admin", password_hash=h)
    assert authenticate("admin", "aus-dem-secret") is not None
    with pytest.raises(ValueError):
        set_user("admin", password_hash="kein-hash")


def test_csrf_wird_erzwungen(app):
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    assert client.post("/login", data={"name": "schuetze", "passwort": "geheim1234"}).status_code == 400
    token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/login").get_data(as_text=True)).group(1)
    resp = client.post("/login", data={"name": "schuetze", "passwort": "geheim1234", "csrf_token": token})
    assert resp.status_code == 302


@pytest.mark.parametrize("ziel", ["//boese.example", "/\\boese.example", "\\\\boese.example",
                                  "https://boese.example/", "javascript:alert(1)", "boese"])
def test_login_next_nur_lokale_pfade(client, ziel):
    resp = client.post("/login", query_string={"next": ziel}, data={"name": "schuetze", "passwort": "geheim1234"})
    ort = resp.headers["Location"]
    # Weiterleitung bleibt auf der eigenen App: relativer Pfad, kein Host, kein Schema
    assert ort.startswith("/") and not ort.startswith("//") and "\\" not in ort
    assert urlparse(ort).netloc == "" and urlparse(ort).scheme == ""


def test_login_next_lokaler_pfad(client):
    resp = client.post("/login?next=/lose", data={"name": "schuetze", "passwort": "geheim1234"})
    assert resp.headers["Location"] == "/lose"
