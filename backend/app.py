"""Flask-App: Routen für Laborierungen, Testserien, Lose, Etiketten und Backup.

Start lokal:  cd backend && python3 app.py
Im Container: gunicorn "app:create_app()"
"""
import json
import secrets
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix

import auth
import backup
import checks
import config
import labels
import storage
from forms import LABORIERUNG_FELDER, LOS_FELDER, TESTSERIE_FELDER, gruppiert, parse_form
from models import STATUS, Foto, Laborierung, Los, Testserie
from storage import Session
from units import fmt_date, fmt_decimal

FRONTEND = config.BASE_DIR / "frontend"
FOTO_ENDUNGEN = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
# Ohne Login erreichbar (Probes, Login, Assets für Login-Seite und PWA-Manifest)
OEFFENTLICH = {"healthz", "readyz", "login", "static", "manifest"}

csrf = CSRFProtect()


def create_app(overrides=None):
    app = Flask(
        __name__,
        template_folder=str(FRONTEND / "templates"),
        static_folder=str(FRONTEND / "static"),
    )
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=config.database_url(),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
        MAX_CONTENT_LENGTH=config.MAX_UPLOAD_MB * 1024 * 1024,
        WTF_CSRF_TIME_LIMIT=None,  # Formular am Schießstand darf lange offen sein
        UPLOAD_DIR=config.UPLOAD_DIR,
        LABEL_SIZE=config.LABEL_SIZE,
        LOGIN_RATE_LIMIT=config.LOGIN_RATE_LIMIT,
    )
    if overrides:
        app.config.update(overrides)
    if not app.config["SECRET_KEY"]:
        app.logger.warning("SECRET_KEY nicht gesetzt – Sessions überleben keinen Neustart.")
        app.config["SECRET_KEY"] = secrets.token_urlsafe(32)
    if config.TRUST_PROXY:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    storage.init_engine(app.config["DATABASE_URL"])
    csrf.init_app(app)
    # In-Memory reicht: ein Replika, ein Gunicorn-Worker (siehe Dockerfile)
    limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")
    auth.login_manager.init_app(app)

    app.jinja_env.filters["dez"] = fmt_decimal
    app.jinja_env.filters["datum"] = fmt_date
    app.jinja_env.globals.update(STATUS=STATUS, hinweise=checks.hinweise, app_version=config.APP_VERSION)

    @app.teardown_appcontext
    def remove_session(exc=None):
        Session.remove()

    @app.before_request
    def login_pflicht():
        if request.endpoint in OEFFENTLICH or current_user.is_authenticated:
            return None
        return auth.login_manager.unauthorized()

    @app.after_request
    def security_header(resp):
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; frame-ancestors 'none'; form-action 'self'",
        )
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    register_routes(app, limiter)
    return app


def _lokal_weiterleiten(url):
    """Weiterleitung nur auf Pfade dieser App (kein Open Redirect), sonst zur Startseite.
    Backslashes entfernen, weil Browser "/\\host" wie "//host" behandeln."""
    url = (url or "").replace("\\", "")
    teile = urlparse(url)
    if url.startswith("/") and not teile.netloc and not teile.scheme:
        return redirect(url)
    return redirect(url_for("index"))


def _get_or_404(model, obj_id):
    obj = Session.get(model, obj_id)
    if obj is None:
        abort(404)
    return obj


def _speichere_fotos(app, serie, dateien):
    upload_dir = Path(app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    for datei in dateien:
        if not datei or not datei.filename:
            continue
        endung = Path(datei.filename).suffix.lower()
        if endung not in FOTO_ENDUNGEN:
            flash(f"Foto „{datei.filename}“ übersprungen: Dateityp nicht erlaubt.", "warnung")
            continue
        name = f"{date.today():%Y/%m}/{uuid.uuid4().hex}{endung}"
        ziel = upload_dir / name
        ziel.parent.mkdir(parents=True, exist_ok=True)
        datei.save(ziel)
        serie.fotos.append(Foto(pfad=name, originalname=datei.filename[:255]))


def _loesche_fotodateien(app, fotos):
    for foto in fotos:
        (Path(app.config["UPLOAD_DIR"]) / foto.pfad).unlink(missing_ok=True)


def register_routes(app, limiter):  # noqa: C901 – bewusst alle Routen an einem Ort
    # ---------- Betrieb ----------
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": config.APP_VERSION}

    @app.get("/readyz")
    def readyz():
        try:
            storage.ping()
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("readyz: DB nicht erreichbar: %s", exc)
            return {"status": "db nicht erreichbar"}, 503
        return {"status": "ok"}

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.webmanifest",
                                   mimetype="application/manifest+json")

    # ---------- Login ----------
    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit(lambda: app.config["LOGIN_RATE_LIMIT"], methods=["POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        if request.method == "POST":
            user = auth.authenticate(request.form.get("name"), request.form.get("passwort"))
            if user:
                login_user(user, remember=False)
                session.permanent = True
                return _lokal_weiterleiten(request.args.get("next"))
            flash("Benutzername oder Passwort falsch.", "fehler")
        return render_template("login.html")

    @app.post("/logout")
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # ---------- Laborierungen ----------
    @app.get("/")
    def index():
        filt = {k: request.args.get(k) or None for k in ("kaliber", "pulver", "status", "suche")}
        return render_template(
            "laborierungen.html",
            laborierungen=storage.laborierungen(**filt),
            filt=filt,
            kaliber_liste=storage.distinct_werte(Laborierung.kaliber),
            pulver_liste=storage.distinct_werte(Laborierung.pulver),
        )

    def _vorschlaege():
        return {
            f: storage.distinct_werte(getattr(Laborierung, f))
            for f in ("kaliber", "geschoss_hersteller", "geschoss_art", "geschoss_oberflaeche",
                      "pulver", "zuendhuetchen", "huelsenmarke", "matrizen")
        }

    def _lab_formular(lab, werte=None, fehler=None, status=200):
        return render_template(
            "laborierung_form.html", lab=lab, gruppen=gruppiert(LABORIERUNG_FELDER),
            werte=werte, fehler=fehler or {}, vorschlaege=_vorschlaege(),
        ), status

    def _lab_speichern(lab):
        werte, fehler = parse_form(LABORIERUNG_FELDER, request.form)
        if fehler:
            flash("Bitte die markierten Felder prüfen.", "fehler")
            return _lab_formular(lab, request.form, fehler, 422)
        werte["status"] = werte.get("status") or "entwurf"
        for k, v in werte.items():
            setattr(lab, k, v)
        Session.add(lab)
        Session.commit()
        for h in checks.hinweise(lab):
            if h.stufe == "warnung":
                flash(h.text, "warnung")
        flash("Gespeichert.", "ok")
        return redirect(url_for("laborierung", lab_id=lab.id))

    @app.route("/laborierung/neu", methods=["GET", "POST"])
    def laborierung_neu():
        lab = Laborierung(status="entwurf", datum=date.today())
        if request.method == "POST":
            return _lab_speichern(lab)
        return _lab_formular(lab)

    @app.get("/laborierung/<int:lab_id>")
    def laborierung(lab_id):
        lab = _get_or_404(Laborierung, lab_id)
        aenderungen = checks.unterschiede(lab.vorgaenger, lab) if lab.vorgaenger else []
        heute = date.today()
        neue_serie = Testserie(datum=heute)
        if lab.vorgaenger and not lab.testserien:
            neue_serie.geaenderte_parameter = checks.unterschiede_text(lab.vorgaenger, lab)
        elif lab.testserien:
            # Waffe/Feder der letzten Serie vorbelegen: am Stand meist gleich
            neue_serie.waffe = lab.testserien[0].waffe
            neue_serie.federstaerke = lab.testserien[0].federstaerke
        return render_template(
            "laborierung_detail.html", lab=lab, gruppen=gruppiert(LABORIERUNG_FELDER),
            aenderungen=aenderungen, neue_serie=neue_serie, test_felder=TESTSERIE_FELDER,
            heute=heute, waffen=storage.distinct_werte(Testserie.waffe),
            nachfolger=Session.query(Laborierung).filter_by(vorgaenger_id=lab.id).all(),
        )

    @app.route("/laborierung/<int:lab_id>/bearbeiten", methods=["GET", "POST"])
    def laborierung_bearbeiten(lab_id):
        lab = _get_or_404(Laborierung, lab_id)
        if request.method == "POST":
            return _lab_speichern(lab)
        return _lab_formular(lab)

    @app.post("/laborierung/<int:lab_id>/duplizieren")
    def laborierung_duplizieren(lab_id):
        kopie = storage.duplizieren(_get_or_404(Laborierung, lab_id))
        Session.commit()
        flash("Kopie angelegt – jetzt die geänderten Parameter eintragen.", "ok")
        return redirect(url_for("laborierung_bearbeiten", lab_id=kopie.id))

    @app.post("/laborierung/<int:lab_id>/loeschen")
    def laborierung_loeschen(lab_id):
        lab = _get_or_404(Laborierung, lab_id)
        if lab.lose:
            flash("Zu dieser Laborierung gibt es noch Lose – bitte zuerst die Lose löschen.", "fehler")
            return redirect(url_for("laborierung", lab_id=lab.id))
        fotos = [f for t in lab.testserien for f in t.fotos]
        Session.delete(lab)
        Session.commit()
        _loesche_fotodateien(app, fotos)
        flash("Laborierung gelöscht.", "ok")
        return redirect(url_for("index"))

    # ---------- Testserien ----------
    @app.post("/laborierung/<int:lab_id>/testserie")
    def testserie_neu(lab_id):
        lab = _get_or_404(Laborierung, lab_id)
        werte, fehler = parse_form(TESTSERIE_FELDER, request.form)
        if fehler:
            for name, text in fehler.items():
                flash(f"{name}: {text}", "fehler")
            return redirect(url_for("laborierung", lab_id=lab.id) + "#erfassen")
        serie = Testserie(**werte)
        lab.testserien.append(serie)
        _speichere_fotos(app, serie, request.files.getlist("fotos"))
        Session.commit()
        flash("Testserie gespeichert.", "ok")
        return redirect(url_for("laborierung", lab_id=lab.id) + f"#serie-{serie.id}")

    @app.route("/testserie/<int:serie_id>/bearbeiten", methods=["GET", "POST"])
    def testserie_bearbeiten(serie_id):
        serie = _get_or_404(Testserie, serie_id)
        fehler = {}
        if request.method == "POST":
            werte, fehler = parse_form(TESTSERIE_FELDER, request.form)
            if not fehler:
                for k, v in werte.items():
                    setattr(serie, k, v)
                _speichere_fotos(app, serie, request.files.getlist("fotos"))
                Session.commit()
                flash("Testserie gespeichert.", "ok")
                return redirect(url_for("laborierung", lab_id=serie.laborierung_id) + f"#serie-{serie.id}")
            flash("Bitte die markierten Felder prüfen.", "fehler")
        return render_template(
            "testserie_form.html", serie=serie, felder=TESTSERIE_FELDER, fehler=fehler,
            werte=request.form if fehler else None, waffen=storage.distinct_werte(Testserie.waffe),
        ), (422 if fehler else 200)

    @app.post("/testserie/<int:serie_id>/loeschen")
    def testserie_loeschen(serie_id):
        serie = _get_or_404(Testserie, serie_id)
        lab_id, fotos = serie.laborierung_id, list(serie.fotos)
        Session.delete(serie)
        Session.commit()
        _loesche_fotodateien(app, fotos)
        flash("Testserie gelöscht.", "ok")
        return redirect(url_for("laborierung", lab_id=lab_id))

    @app.get("/fotos/<path:pfad>")
    def foto(pfad):
        return send_from_directory(app.config["UPLOAD_DIR"], pfad)

    @app.post("/foto/<int:foto_id>/loeschen")
    def foto_loeschen(foto_id):
        foto_obj = _get_or_404(Foto, foto_id)
        serie_id = foto_obj.testserie_id
        Session.delete(foto_obj)
        Session.commit()
        _loesche_fotodateien(app, [foto_obj])
        return redirect(url_for("testserie_bearbeiten", serie_id=serie_id))

    # ---------- Lose ----------
    @app.get("/lose")
    def lose():
        alle = Session.query(Los).order_by(Los.datum.desc(), Los.id.desc()).all()
        return render_template("lose.html", lose=alle)

    @app.post("/laborierung/<int:lab_id>/los")
    def los_neu(lab_id):
        lab = _get_or_404(Laborierung, lab_id)
        werte, fehler = parse_form(LOS_FELDER, request.form)
        if fehler:
            for name, text in fehler.items():
                flash(f"Los – {name}: {text}", "fehler")
            return redirect(url_for("laborierung", lab_id=lab.id) + "#lose")
        los_nr = storage.naechste_los_nr(lab.kaliber, werte["datum"].year)
        los = Los(laborierung=lab, los_nr=los_nr, **werte)
        Session.add(los)
        try:
            Session.commit()
        except IntegrityError:
            Session.rollback()
            flash("Los-Nr. war gerade vergeben – bitte erneut speichern.", "fehler")
            return redirect(url_for("laborierung", lab_id=lab.id) + "#lose")
        flash(f"Los {los.los_nr} angelegt.", "ok")
        return redirect(url_for("laborierung", lab_id=lab.id) + "#lose")

    @app.route("/los/<int:los_id>/bearbeiten", methods=["GET", "POST"])
    def los_bearbeiten(los_id):
        los = _get_or_404(Los, los_id)
        fehler = {}
        if request.method == "POST":
            werte, fehler = parse_form(LOS_FELDER, request.form)
            if not fehler:
                for k, v in werte.items():
                    setattr(los, k, v)
                Session.commit()
                flash("Los gespeichert.", "ok")
                return redirect(url_for("laborierung", lab_id=los.laborierung_id) + "#lose")
        return render_template("los_form.html", los=los, felder=LOS_FELDER, fehler=fehler,
                               werte=request.form if fehler else None), (422 if fehler else 200)

    @app.post("/los/<int:los_id>/loeschen")
    def los_loeschen(los_id):
        los = _get_or_404(Los, los_id)
        lab_id = los.laborierung_id
        Session.delete(los)
        Session.commit()
        flash(f"Los {los.los_nr} gelöscht.", "ok")
        return redirect(url_for("laborierung", lab_id=lab_id) + "#lose")

    def _etikett_parameter():
        breite, hoehe = labels.parse_size(request.args.get("groesse"), app.config["LABEL_SIZE"])
        # Checkbox + Hidden-Feld schicken qr=0&qr=1; ohne Parameter ist QR an
        qr_werte = request.args.getlist("qr")
        mit_qr = "1" in qr_werte if qr_werte else True
        return breite, hoehe, mit_qr, request.args.get("bogen") == "1"

    def _qr_ziel(los):
        return url_for("laborierung", lab_id=los.laborierung_id, _external=True)

    @app.get("/los/<int:los_id>/etikett")
    def los_etikett(los_id):
        los = _get_or_404(Los, los_id)
        breite, hoehe, mit_qr, bogen = _etikett_parameter()
        qr = labels.qr_svg(_qr_ziel(los)) if mit_qr else None
        cols, rows = labels.bogen_raster(breite, hoehe)
        return render_template(
            "etikett.html", los=los, daten=labels.etikett_daten(los), qr=qr,
            breite=breite, hoehe=hoehe, bogen=bogen, anzahl=cols * rows if bogen else 1,
            cols=cols, rand=labels.BOGEN_RAND_MM, mit_qr=mit_qr,
        )

    @app.get("/los/<int:los_id>/etikett.pdf")
    def los_etikett_pdf(los_id):
        los = _get_or_404(Los, los_id)
        breite, hoehe, mit_qr, bogen = _etikett_parameter()
        qr_url = _qr_ziel(los) if mit_qr else None
        pdf = labels.etikett_pdf(los, breite, hoehe, qr_url=qr_url, bogen=bogen)
        return Response(pdf, mimetype="application/pdf", headers={
            "Content-Disposition": f'inline; filename="etikett-{los.los_nr}.pdf"',
        })

    # ---------- Backup ----------
    @app.get("/backup")
    def backup_seite():
        return render_template("backup.html")

    @app.get("/backup/export.json")
    def export_json():
        return Response(backup.export_json(), mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="ladedaten-{date.today()}.json"',
        })

    @app.get("/backup/export-csv.zip")
    def export_csv():
        return Response(backup.export_csv_zip(), mimetype="application/zip", headers={
            "Content-Disposition": f'attachment; filename="ladedaten-csv-{date.today()}.zip"',
        })

    @app.post("/backup/import")
    def backup_import():
        datei = request.files.get("datei")
        if not datei or not datei.filename:
            flash("Keine Datei ausgewählt.", "fehler")
            return redirect(url_for("backup_seite"))
        raw = datei.read()
        try:
            if datei.filename.lower().endswith(".zip"):
                daten = backup.csv_zip_zu_daten(raw)
            else:
                daten = json.loads(raw.decode("utf-8-sig"))
            stat = backup.importiere(daten)
            Session.commit()
        except (ValueError, KeyError, TypeError, IntegrityError) as exc:
            Session.rollback()
            flash(f"Import fehlgeschlagen: {exc}", "fehler")
            return redirect(url_for("backup_seite"))
        flash(
            f"Importiert: {stat['laborierungen']} Laborierungen, {stat['testserien']} Testserien, "
            f"{stat['lose']} Lose ({stat['lose_uebersprungen']} Lose mit vorhandener Nr. übersprungen).",
            "ok",
        )
        return redirect(url_for("index"))

    @app.errorhandler(413)
    def zu_gross(_):
        flash(f"Datei zu groß (max. {config.MAX_UPLOAD_MB} MB).", "fehler")
        # Nur den Pfad des Referers verwenden, nie einen fremden Host
        return _lokal_weiterleiten(urlparse(request.referrer or "").path)


if __name__ == "__main__":
    # Nur lokale Entwicklung. Debugger nur mit FLASK_DEBUG=1 und standardmäßig nur
    # auf localhost (für Tests am Handy im WLAN: HOST=0.0.0.0, dann ohne Debugger).
    create_app().run(
        host=config.get("HOST", "127.0.0.1"),
        port=int(config.get("PORT", "8000")),
        debug=config.get_bool("FLASK_DEBUG", False),
    )
