#!/usr/bin/env bash
# Startet (oder erstellt) den lokalen MariaDB-Container für die Ladedaten-App via Podman.
set -euo pipefail
cd "$(dirname "$0")/.."

# .env laden
set -a
source .env
set +a

CONTAINER_NAME="ladedaten-mariadb"
VOLUME_NAME="ladedaten_mariadb"

if podman container exists "$CONTAINER_NAME"; then
  echo "Container '$CONTAINER_NAME' existiert bereits, starte ihn..."
  podman start "$CONTAINER_NAME"
else
  echo "Erstelle Volume '$VOLUME_NAME' (falls noch nicht vorhanden)..."
  podman volume create "$VOLUME_NAME" >/dev/null || true

  echo "Erstelle und starte Container '$CONTAINER_NAME'..."
  podman run -d \
    --name "$CONTAINER_NAME" \
    -e MARIADB_ROOT_PASSWORD="$DB_ROOT_PASSWORD" \
    -e MARIADB_DATABASE="$DB_NAME" \
    -e MARIADB_USER="$DB_USER" \
    -e MARIADB_PASSWORD="$DB_PASSWORD" \
    -p "${DB_PORT}:3306" \
    -v "${VOLUME_NAME}:/var/lib/mysql" \
    docker.io/library/mariadb:11 \
    --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
fi

echo "Warte auf MariaDB..."
for i in $(seq 1 60); do
  if podman exec "$CONTAINER_NAME" healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then
    echo "MariaDB ist bereit (127.0.0.1:${DB_PORT}). Schema anlegen mit:"
    echo "  venv/bin/python backend/manage.py migrate"
    exit 0
  fi
  sleep 1
done
echo "Timeout beim Warten auf MariaDB." >&2
exit 1
