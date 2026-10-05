# Ladedaten

Webanwendung zur Verwaltung eigener Wiederlade-Daten (Laborierungen,
Testserien/Erfahrungen, Lose mit Etikettendruck). Flask + MariaDB, Betrieb auf
Kubernetes per Helm, für die Bedienung am Handy gebaut.

> Das Tool gibt **keine** Ladedaten vor. Es dokumentiert nur eigene Angaben aus
> Ladetabellen und warnt, wenn die eingetragene Ladung über der eingetragenen
> Max-Ladung der Quelle liegt.

## Lokal entwickeln

Voraussetzungen: Python 3.12+, Podman.

```bash
cp .env.example .env              # Passwörter, SECRET_KEY, ADMIN_* eintragen
./db/run_mariadb.sh               # MariaDB 11 im Podman-Container
python3 -m venv venv
venv/bin/pip install -r requirements-dev.txt
venv/bin/python backend/manage.py migrate   # Schema + Admin + Beispieldaten
cd backend && ../venv/bin/python app.py     # http://localhost:8000
```

Ohne MariaDB geht es zum Ausprobieren auch mit SQLite:
`DATABASE_URL=sqlite:///data/dev.db` in `.env`.

Tests und Lint:

```bash
venv/bin/pytest
venv/bin/ruff check .
```

## docker compose (App + MariaDB)

```bash
cp .env.example .env    # DB_PASSWORD, DB_ROOT_PASSWORD, ADMIN_PASSWORD setzen
docker compose up --build        # oder: podman compose up --build
# http://localhost:8000
```

Der Dienst `migrate` läuft vor der App und ist idempotent.

## Benutzer

Es gibt keine Registrierung. Benutzer entstehen auf zwei Wegen:

- über `ADMIN_USERNAME` und `ADMIN_PASSWORD_HASH` (oder lokal `ADMIN_PASSWORD`).
  Das wird bei jedem `manage.py migrate` gesetzt, die Umgebung bzw. das Secret
  ist also die Quelle der Wahrheit.
- mit `python backend/manage.py create-user NAME` (fragt das Passwort ab).

Den Hash für das Kubernetes-Secret erzeugt `python backend/manage.py hash-password`.

## Kubernetes / Helm

Image und Chart veröffentlicht die CI in der GitHub Container Registry:

- Image: `ghcr.io/iamrfc1918/reloading-database:<version>` (amd64 + arm64)
- Chart: `oci://ghcr.io/iamrfc1918/charts/ladedaten`

```bash
# values-example.yaml kopieren, Host und Passwort-Hash anpassen
helm install ladedaten oci://ghcr.io/iamrfc1918/charts/ladedaten --version 0.1.0 \
  -n ladedaten --create-namespace -f values-example.yaml

# oder direkt aus dem Repo
helm install ladedaten charts/ladedaten -n ladedaten --create-namespace \
  -f charts/ladedaten/values-example.yaml
```

Ist das GHCR-Paket privat, braucht der Cluster ein Pull-Secret (siehe
`values-example.yaml`). Alternativ stellst du das Paket unter
GitHub → Packages → Package settings auf „public“.

Wichtige Werte (Details in `charts/ladedaten/values.yaml`):

| Wert | Bedeutung |
|---|---|
| `database.mode` | `operator` (Standard, mariadb-operator), `internal` (einfaches StatefulSet) oder `external` |
| `database.operator.createInstance` | `true`: eigene MariaDB-Instanz, `false`: vorhandene über `mariaDbRef` mitbenutzen |
| `database.external.existingSecret` | Secret mit `host`, `port`, `database`, `username`, `password` |
| `auth.adminPasswordHash` / `auth.existingSecret` | Login (Argon2-Hash) |
| `ingress.host`, `ingress.tls`, `ingress.certManager` | Erreichbarkeit/TLS |
| `global.imageRegistry`, `imagePullSecrets` | Betrieb ohne Internet (interner Mirror) |
| `networkPolicy.enabled` | App darf nur DNS + DB, DB nur von App/Backup |
| `backup.enabled` | täglicher logischer Dump auf eigenes PVC (Operator: `Backup`-CR, sonst CronJob) |

Migrationen laufen im Init-Container `migrate` bei jedem Pod-Start.

### mariadb-operator

Mit `database.mode: operator` (Voraussetzung: [mariadb-operator](https://github.com/mariadb-operator/mariadb-operator)
mit den CRDs `k8s.mariadb.com/v1alpha1`) legt das Chart an:

- optional eine eigene `MariaDB`-Instanz (utf8mb4, PVC, Root-Passwort generiert)
- `Database`, `User` (Passwort-Secret `<release>-db`, wird generiert) und `Grant`
  (`ALL PRIVILEGES` nur auf die App-Datenbank)
- bei `backup.enabled` einen `Backup`-CR (nur die App-Datenbank, gzip, PVC)

`cleanupPolicy: Skip` und `helm.sh/resource-policy: keep` sorgen dafür, dass
Daten ein `helm uninstall` überleben. Die DB-Verbindung ist bewusst
unverschlüsselt (nur clusterintern, per NetworkPolicy eingrenzbar).

## CI/CD und Releases (GitHub Actions)

`.github/workflows/ci.yml` läuft bei jedem Push, Pull Request und Tag:

1. ruff, pytest, `alembic check`, Migration gegen einen MariaDB-11.4-Service,
   `helm lint`/`helm template`
2. Trivy auf das Repo (Abhängigkeiten, Secrets, Dockerfile/Helm-Misconfig) und
   auf das gebaute Image. Behebbare **CRITICAL/HIGH** lassen den Build
   scheitern. Alle Funde gehen als SARIF in den Security-Tab, dazu SBOM
   (CycloneDX) als Artefakt.
3. Image nach GHCR: `main` → `:edge`, `:sha-…`; Tag `vX.Y.Z` → `:X.Y.Z`,
   `:X.Y`, `:latest` (ab 1.0 zusätzlich `:X`)
4. Nur bei Tags: Chart als OCI nach GHCR und GitHub-Release mit Chart-Paket
   und generierten Release Notes

Versioniert wird nach [Semantic Versioning](https://semver.org/lang/de/).
Die Version steht in `charts/ladedaten/Chart.yaml` (`version` = `appVersion`),
und die CI prüft, dass der Tag dazu passt. Ein Release legt das Skript an:

```bash
scripts/release.sh 0.2.0        # setzt Chart.yaml, committet, legt Tag v0.2.0 an
git push origin main v0.2.0     # startet Build + Release
```

Pre-Releases (`0.3.0-rc.1`) werden als solche markiert und bekommen kein
`:latest`. Die laufende Version zeigen `/healthz` und die Fußzeile.
Dependabot hält Actions, Python-Pakete und Basis-Image aktuell.

## Bedienung am Handy

- Als App installieren: im Browser „Zum Startbildschirm hinzufügen“.
- Erfahrungen am Stand erfassen: Laborierung öffnen und **+ Erfahrung** tippen.
- Etiketten: In der Detailansicht beim Los auf **Aufkleber drucken** (Druck-CSS,
  Größe einstellbar) oder **PDF** tippen. Vom Handy aus ist das PDF meist der
  einfachere Weg.
- Backup: unter **Backup** als JSON oder CSV-ZIP exportieren und importieren.
