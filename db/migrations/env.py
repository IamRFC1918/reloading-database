"""Alembic-Umgebung. Normalerweise übergibt `manage.py migrate` eine offene
Verbindung; direkter Aufruf (`alembic -c db/alembic.ini ...`) nutzt config.py."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import config as app_config
from models import Base

cfg = context.config
if cfg.config_file_name and not cfg.attributes.get("connection"):
    fileConfig(cfg.config_file_name)


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


connection = cfg.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    with create_engine(app_config.database_url()).connect() as conn:
        run(conn)
        conn.commit()
