# Basis: Wolfi (Chainguard) – glibc, minimal, täglich neu gebaute Pakete,
# dadurch kaum offene CVEs. Python wird als Paket in fester Minor-Version
# installiert. Der Digest wird von Dependabot aktualisiert.
ARG BASE=cgr.dev/chainguard/wolfi-base:latest@sha256:9c2092b053779e14c82fb50f77b37bcc38b7d2c83972352d5813280f9d035b03

# ---------- Build: Abhängigkeiten in ein venv installieren ----------
FROM ${BASE} AS build
RUN apk add --no-cache python-3.12 py3.12-pip
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python3.12 -m venv /venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /venv/bin/pip install -r /tmp/requirements.txt \
    && /venv/bin/pip uninstall -y pip

# ---------- Laufzeit ----------
FROM ${BASE}
# Nur der Interpreter, kein pip. apk/busybox bleiben (Teil von wolfi-base):
# Als Non-root mit read-only Root-FS kann apk nichts installieren.
RUN apk add --no-cache python-3.12 \
    && mkdir -p /data/fotos && chown -R 10001:10001 /data
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    UPLOAD_DIR=/data/fotos \
    PORT=8000

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

# Kein Benutzer-Eintrag nötig: numerische UID/GID (passt zu runAsUser im Chart)
USER 10001:10001
WORKDIR /app/backend
EXPOSE 8000
VOLUME ["/data"]

# Für docker/podman (Kubernetes nutzt die Probes aus dem Chart). Ohne curl im Image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"]

# Ein Worker mit Threads: Rate-Limiter speichert im Prozess-Speicher (ein Replika).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", \
     "--timeout", "60", "--worker-tmp-dir", "/tmp", "--access-logfile", "-", "app:create_app()"]
