"""Login: wenige feste Benutzer, Passwort-Hash mit Argon2.

Benutzer entstehen per `manage.py create-user` oder beim Start aus
ADMIN_USERNAME + ADMIN_PASSWORD_HASH (Kubernetes-Secret). Eine
Registrierung über die Oberfläche gibt es bewusst nicht.
"""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from flask_login import LoginManager
from sqlalchemy import select

from models import Benutzer
from storage import Session

hasher = PasswordHasher()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = "Bitte anmelden."
login_manager.login_message_category = "info"

# Gegen Timing-Angriffe: auch bei unbekanntem Benutzer einmal hashen
_DUMMY_HASH = hasher.hash("dummy-passwort")


@login_manager.user_loader
def load_user(user_id):
    return Session.get(Benutzer, int(user_id))


def hash_password(password):
    if len(password) < 8:
        raise ValueError("Passwort muss mindestens 8 Zeichen lang sein.")
    return hasher.hash(password)


def authenticate(name, password):
    user = Session.scalar(select(Benutzer).where(Benutzer.name == (name or "").strip()))
    try:
        hasher.verify(user.passwort_hash if user else _DUMMY_HASH, password or "")
    except (VerificationError, InvalidHashError):
        return None
    if user is None:
        return None
    if hasher.check_needs_rehash(user.passwort_hash):
        user.passwort_hash = hasher.hash(password)
        Session.commit()
    return user


def set_user(name, password=None, password_hash=None):
    """Legt den Benutzer an oder setzt sein Passwort neu (idempotent)."""
    if password_hash:
        if not password_hash.startswith("$argon2"):
            raise ValueError("ADMIN_PASSWORD_HASH ist kein Argon2-Hash.")
    else:
        password_hash = hash_password(password or "")
    user = Session.scalar(select(Benutzer).where(Benutzer.name == name))
    if user is None:
        user = Benutzer(name=name, passwort_hash=password_hash)
        Session.add(user)
    elif user.passwort_hash != password_hash:
        user.passwort_hash = password_hash
    Session.commit()
    return user
