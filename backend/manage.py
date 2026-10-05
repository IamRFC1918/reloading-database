"""Verwaltungskommandos.

  python manage.py migrate          DB-Schema aktualisieren (idempotent), Admin aus
                                    ADMIN_* anlegen/aktualisieren, ggf. Beispieldaten
  python manage.py create-user NAME Benutzer anlegen / Passwort setzen (fragt interaktiv)
  python manage.py hash-password    Argon2-Hash fürs Kubernetes-Secret ausgeben
  python manage.py seed             Beispieldaten anlegen (nur wenn DB leer)
"""
import argparse
import getpass
import sys

from alembic import command
from alembic.config import Config

import auth
import config
import seed
import storage

ALEMBIC_INI = config.BASE_DIR / "db" / "alembic.ini"


def _passwort_abfragen():
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    pw = getpass.getpass("Passwort: ")
    if pw != getpass.getpass("Passwort wiederholen: "):
        sys.exit("Passwörter stimmen nicht überein.")
    return pw


def migrate(url):
    engine = storage.init_engine(url)
    storage.wait_for_db(engine, config.DB_WAIT_SECONDS)
    cfg = Config(str(ALEMBIC_INI))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    if config.ADMIN_USERNAME and (config.ADMIN_PASSWORD_HASH or config.ADMIN_PASSWORD):
        auth.set_user(config.ADMIN_USERNAME, password=config.ADMIN_PASSWORD,
                      password_hash=config.ADMIN_PASSWORD_HASH)
        print(f"Benutzer '{config.ADMIN_USERNAME}' aus Umgebung gesetzt.")
    if config.SEED_DEMO_DATA and seed.seed_demo_daten():
        print("Beispieldaten angelegt.")
    print("Migration abgeschlossen.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    p_user = sub.add_parser("create-user")
    p_user.add_argument("name")
    sub.add_parser("hash-password")
    sub.add_parser("seed")
    args = parser.parse_args(argv)
    url = config.database_url()

    if args.cmd == "migrate":
        migrate(url)
    elif args.cmd == "hash-password":
        print(auth.hash_password(_passwort_abfragen()))
    else:
        storage.init_engine(url)
        if args.cmd == "create-user":
            auth.set_user(args.name, password=_passwort_abfragen())
            print(f"Benutzer '{args.name}' gespeichert.")
        elif args.cmd == "seed":
            print("Beispieldaten angelegt." if seed.seed_demo_daten() else "DB nicht leer – nichts getan.")


if __name__ == "__main__":
    main()
