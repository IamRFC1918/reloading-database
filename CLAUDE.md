# Ladedaten

Private Webapp (Flask + MariaDB) zur Dokumentation eigener Wiederlade-Daten
(Sportschütze, .45 ACP): Laborierungen, Testserien/Erfahrungen vom Schießstand,
Lose mit Etikettendruck. Läuft auf Kubernetes (eigenes Helm-Chart), wird
überwiegend vom Handy bedient. Oberfläche deutsch, Dezimalkomma, gr/mm.

## Architektur

```
backend/
  app.py        create_app() + alle Routen (Server-Side-Rendering, Jinja2)
  config.py     .env-Loader; Umgebungsvariablen haben Vorrang vor .env
  models.py     SQLAlchemy-2-Modelle (Benutzer, Laborierung, Testserie, Foto, Los)
  storage.py    Engine/scoped Session, Filter, Duplizieren, Los-Nr.-Vergabe
  forms.py      Felddefinitionen (eine Liste pro Entität) + parse_form()
  checks.py     Warnungen (Ladung > Max-Ladung, fehlende Quelle) und Vorserien-Diff
  units.py      Dezimalkomma parsen/formatieren, Datum
  labels.py     Etikettdaten, QR (qrcode), PDF (reportlab), A4-Bogen-Raster
  backup.py     Export/Import JSON und CSV-ZIP
  auth.py       Flask-Login + Argon2, set_user() (idempotent)
  seed.py       Beispieldaten (nur in leere DB)
  manage.py     migrate | create-user | hash-password | seed
frontend/
  templates/    Jinja2; macros.html rendert Felder generisch aus forms.py
  static/       style.css (mobile-first), etikett.css (Druck), app.js, manifest, icons
db/
  alembic.ini, migrations/   Alembic (Revisionen von Hand nummeriert: 0001, 0002 ...)
  run_mariadb.sh             lokale MariaDB 11 via Podman
charts/ladedaten/            Helm-Chart (App, MariaDB-StatefulSet, Backup, NetworkPolicy)
tests/                       pytest gegen SQLite (tmp-Datei pro Test)
.github/workflows/ci.yml     CI/CD (Lint, Tests, MariaDB, Helm, Trivy, GHCR, Release)
scripts/release.sh           SemVer-Release: Chart.yaml setzen, committen, taggen
```

## Start-Befehle

```bash
./db/run_mariadb.sh                          # MariaDB (Podman), liest .env
venv/bin/python backend/manage.py migrate    # Schema, Admin aus ADMIN_*, Seed
cd backend && ../venv/bin/python app.py      # http://localhost:8000
venv/bin/pytest && venv/bin/ruff check .
podman compose up --build                    # App + MariaDB komplett
scripts/release.sh 0.2.0 && git push origin main v0.2.0   # Release
helm lint charts/ladedaten --strict -f charts/ladedaten/values-example.yaml
```

Neue Migration: Modell ändern, dann
`DATABASE_URL=sqlite:///x.db alembic -c db/alembic.ini upgrade head` und
`... revision --autogenerate -m "..." --rev-id 0002`. Die Revision prüfen, vor
allem `server_default=sa.func.now()` statt SQLite-spezifischem Text. CI führt
`alembic check` aus.

## Datenmodell

- `laborierung`: alle Ladeparameter. Dezimalwerte sind `Numeric(7,3)` und
  `Decimal` (gr, mm). `status` ist entwurf/in_test/freigegeben/verworfen.
  `vorgaenger_id` wird beim Duplizieren gesetzt, daraus entsteht der Diff
  „Änderungen ggü. Vorserie“.
- `testserie` (n:1, CASCADE): Erfahrung vom Stand. `schlitten_schliesst` ist
  ein nullable Bool (ja/nein/unbekannt).
- `foto` (n:1 zur Testserie, CASCADE): nur der Pfad relativ zu `UPLOAD_DIR`,
  die Datei liegt auf dem PVC.
- `los` (n:1, RESTRICT): `los_nr` ist eindeutig, Format
  `<KALIBER-ALNUM>-<JAHR>-<NNN>`, fortlaufend je Kaliber und Jahr.
- `benutzer`: Name + Argon2-Hash.
- Alle Tabellen sind utf8mb4 / utf8mb4_unicode_ci (in `MARIADB_TABLE_ARGS`).

## Bewusste Design-Entscheidungen

- **Keine Ladedaten-Vorgaben.** Die Warnung vergleicht nur Ladung mit der
  selbst eingetragenen Max-Ladung der Quelle (`checks.py`). Das Tool soll keine
  „empfohlenen“ Werte, Tabellen oder Hochrechnungen bekommen.
- **Migration im Init-Container statt Helm-Hook.** Bei der mitgelieferten
  MariaDB existiert die DB zum pre-install-Zeitpunkt noch nicht.
  `manage.py migrate` wartet auf die DB (`DB_WAIT_SECONDS`) und ist idempotent.
- **Releases nur über Tags `vX.Y.Z`** (SemVer). `Chart.yaml` `version` und
  `appVersion` sind immer gleich, die CI bricht sonst ab. Image-Tag =
  appVersion, daher braucht `values.yaml` keinen festen Tag. Immer
  `scripts/release.sh` benutzen, nie Tags von Hand setzen.
- **CI-Actions sind auf Commit-SHAs gepinnt** (Kommentar mit Versionsnummer).
  Updates kommen über Dependabot. Trivy-Version steht in `TRIVY_VERSION`.
- **Ein Replika, ein Gunicorn-Worker mit Threads**: RWO-PVC für Fotos,
  Flask-Limiter speichert im Prozess-Speicher (`memory://`). Für mehrere
  Replikas bräuchte es Redis + RWX-Storage.
- **Öffentliche Routen**: `/login`, `/healthz`, `/readyz` (Probe),
  `/static/*` und `/manifest.webmanifest`. Der Browser lädt das Manifest ohne
  Cookies, und statische Assets enthalten keine Daten. Alles andere läuft über
  `login_pflicht()` in `app.py`.
- **Formulare ohne WTForms-Klassen**: Feldlisten in `forms.py` treiben Formular,
  Parsing, Detailansicht und Vorserien-Diff. Ein neues Feld braucht also Modell,
  Migration und einen `Feld(...)`-Eintrag. CSRF kommt global von CSRFProtect.
- **Dezimalfelder sind `type=text inputmode=decimal`**, nicht `type=number`,
  weil `type=number` mit Komma je nach Browser-Locale unzuverlässig ist.
- **Admin aus dem Secret überschreibt das Passwort bei jedem Start.** Das
  Secret ist die Quelle der Wahrheit.
- **Etikett doppelt**: Druck-CSS (`etikett.html`, `@page` mit Parametergröße)
  und reportlab-PDF (`labels.py`) nutzen dieselben `etikett_daten()`. Im PDF
  werden Zeichen außerhalb von cp1252 (Emojis) weggelassen, weil die
  Standardschriften sie nicht darstellen.
- **Import legt immer neue Datensätze an** (keine Merges/Upserts). Lose mit
  vorhandener Los-Nr. werden übersprungen. Fotos sind nicht im Export.
- Sicherheits-Header: CSP ohne Inline-Skripte (`script-src 'self'`). Inline-
  Styles sind erlaubt (nötig für die dynamische `@page`-Größe).

## Verifiziert

- pytest (54 Tests: Modelle, Warnlogik, Login/CSRF/Rate-Limit, Routen,
  Etikett/PDF, Backup-Roundtrip) gegen SQLite.
- Mit Podman gegen MariaDB 11 und 11.4: Migration idempotent, utf8mb4 inkl.
  Emoji, App mit `--read-only --user 10001 --cap-drop ALL`, MariaDB mit
  `--read-only --user 999` und tmpfs für `/run/mysqld` und `/tmp`, Backup-Skript
  inkl. Rotation.
- `helm lint --strict` und `helm template` (internal/external, Backup,
  NetworkPolicy, Mirror-Registry).

## Offene Punkte

- Das Helm-Chart lief noch nicht in einem echten Cluster (nur lint/template
  sowie die Container-Settings mit Podman).
- Fotos werden in Originalgröße gespeichert (kein Verkleinern, EXIF bleibt).
  Das Foto-PVC ist nicht im Backup-CronJob enthalten.
- Keine Offline-Fähigkeit/Service-Worker (bewusst nicht in Version 1).
- Das Debian-Basisimage (python:3.12-slim, Debian 13) hat unbehobene HIGH-CVEs
  (util-linux, ncurses, systemd-libs, perl). Das Trivy-Gate ignoriert sie
  (`ignore-unfixed`). Langfristig wäre ein distroless- oder Chainguard-Basisimage
  eine Option.
- SARIF-Upload in den Security-Tab braucht bei privaten Repos GitHub Advanced
  Security (Schritt ist `continue-on-error`).
- Kein UI zum Ändern des eigenen Passworts (nur `manage.py create-user`).
