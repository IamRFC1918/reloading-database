# ---------- Build: Abhängigkeiten in ein venv installieren ----------
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install -r /tmp/requirements.txt \
    && /venv/bin/pip uninstall -y pip

# ---------- Laufzeit ----------
FROM python:3.12-slim
# Sicherheitsupdates des Basis-Images mitnehmen; pip wird zur Laufzeit nicht gebraucht
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip setuptools wheel
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    UPLOAD_DIR=/data/fotos \
    PORT=8000

RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/fotos && chown -R 10001:10001 /data

COPY --from=build /venv /venv
WORKDIR /app
COPY backend/ backend/
COPY frontend/ frontend/
COPY db/alembic.ini db/alembic.ini
COPY db/migrations/ db/migrations/

# Von der CI aus dem Git-Tag gesetzt (Semantic Versioning, ohne "v").
# Erst hier, damit eine neue Version nicht den Layer-Cache darüber invalidiert.
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION

USER 10001
WORKDIR /app/backend
EXPOSE 8000
VOLUME ["/data"]

# Ein Worker mit Threads: Rate-Limiter speichert im Prozess-Speicher (ein Replika).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--timeout", "60", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "app:create_app()"]
