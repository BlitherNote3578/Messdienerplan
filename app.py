from flask import Flask, render_template, request, redirect, url_for, session, flash
import csv
import os
from datetime import datetime
import logging

# Logging für Debugging aktivieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Sicherheit: Secret Key und Admin-Passwort aus Umgebungsvariablen
try:
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-nur-fuer-lokale-entwicklung')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'adminpass')

    # Debug-Info (nur für Entwicklung)
    logger.info(f"SECRET_KEY gesetzt: {'Ja' if os.environ.get('SECRET_KEY') else 'Nein (Fallback)'}")
    logger.info(f"ADMIN_PASSWORD gesetzt: {'Ja' if os.environ.get('ADMIN_PASSWORD') else 'Nein (Fallback)'}")

except Exception as e:
    logger.error(f"Fehler beim Laden der Umgebungsvariablen: {e}")
    app.secret_key = 'fallback-key-for-emergency'
    ADMIN_PASSWORD = 'adminpass'

# Sicherstellen, dass das data-Verzeichnis existiert
if not os.path.exists('data'):
    os.makedirs('data')


# Datenbank (SQLAlchemy) Setup
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Lokale SQLite-Datei als Fallback
    sqlite_path = os.path.abspath(os.path.join('data', 'app.db'))
    DATABASE_URL = f'sqlite:///{sqlite_path}'
else:
    # Robustheit für Render/Heroku URLs
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
    elif DATABASE_URL.startswith('postgresql://') and '+psycopg' not in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class PlanEntry(Base):
    __tablename__ = 'plan_entries'
    id = Column(Integer, primary_key=True)
    datum = Column(String(50), nullable=True)
    messdiener_text = Column(Text, nullable=True)
    art_uhrzeit = Column(String(100), nullable=True)


class Queue(Base):
    __tablename__ = 'queues'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)


class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True)
    person = Column(String(100), nullable=False)
    queue_id = Column(Integer, ForeignKey('queues.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(String(32), nullable=True)

    queue = relationship('Queue')


def init_db_and_migrate():
    # Tabellen anlegen
    Base.metadata.create_all(engine)
    from sqlalchemy import select, func
    session = SessionLocal()
    try:
        # Plan migrieren, falls leer
        plan_count = session.query(func.count(PlanEntry.id)).scalar()
        if plan_count == 0:
            plan_csv_path = os.path.join('data', 'plan.csv')
            if os.path.exists(plan_csv_path):
                try:
                    with open(plan_csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        for row in rows[1:]:
                            datum = row[0] if len(row) > 0 else ''
                            messdiener_text = row[1] if len(row) > 1 else ''
                            art = row[2] if len(row) > 2 else ''
                            session.add(PlanEntry(datum=datum, messdiener_text=messdiener_text, art_uhrzeit=art))
                    session.commit()
                except Exception as e:
                    logger.warning(f"Konnte plan.csv nicht migrieren: {e}")
            else:
                # Standardwerte anlegen
                defaults = [
                    PlanEntry(datum='27.07.2024', messdiener_text='', art_uhrzeit='Gottesdienst 10:00'),
                    PlanEntry(datum='03.08.2024', messdiener_text='', art_uhrzeit=''),
                    PlanEntry(datum='10.08.2024', messdiener_text='', art_uhrzeit=''),
                ]
                session.add_all(defaults)
                session.commit()

        # Queues migrieren, falls leer
        from sqlalchemy import func as sa_func
        queue_count = session.query(sa_func.count(Queue.id)).scalar()
        if queue_count == 0:
            queues_csv = os.path.join('data', 'queues.csv')
            if os.path.exists(queues_csv):
                try:
                    with open(queues_csv, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        for row in rows[1:]:
                            if not row:
                                continue
                            try:
                                qid = int(row[0])
                            except Exception:
                                qid = None
                            name = row[1] if len(row) > 1 else 'Unbenannt'
                            q = Queue(name=name)
                            if qid is not None:
                                q.id = qid
                            session.add(q)
                    session.commit()
                except Exception as e:
                    logger.warning(f"Konnte queues.csv nicht migrieren: {e}")

        # Enrollments migrieren, falls leer
        enroll_count = session.query(sa_func.count(Enrollment.id)).scalar()
        if enroll_count == 0:
            enroll_csv = os.path.join('data', 'enrollments.csv')
            if os.path.exists(enroll_csv):
                try:
                    with open(enroll_csv, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        for row in rows[1:]:
                            if len(row) < 2:
                                continue
                            person = (row[0] or '').strip()
                            try:
                                qid = int(row[1])
                            except Exception:
                                continue
                            ts = row[2] if len(row) > 2 else ''
                            session.add(Enrollment(person=person, queue_id=qid, timestamp=ts))
                    session.commit()
                except Exception as e:
                    logger.warning(f"Konnte enrollments.csv nicht migrieren: {e}")
    finally:
        session.close()


# DB initialisieren
init_db_and_migrate()

# DB-Helper für Plan als 2D-Liste (kompatibel zu Templates)
def get_plan_list():
    session = SessionLocal()
    try:
        entries = session.query(PlanEntry).order_by(PlanEntry.id.asc()).all()
        plan = [['Datum', 'Messdiener', 'Art/Uhrzeit']]
        for e in entries:
            plan.append([e.datum or '', e.messdiener_text or '', e.art_uhrzeit or ''])
        return plan
    finally:
        session.close()


def save_plan_db(plan_rows):
    # plan_rows: [['Datum','Messdiener','Art/Uhrzeit'], [datum, mess, art], ...]
    session = SessionLocal()
    try:
        # Alles ersetzen
        session.query(PlanEntry).delete()
        for row in plan_rows[1:]:
            datum = row[0] if len(row) > 0 else ''
            mess = row[1] if len(row) > 1 else ''
            art = row[2] if len(row) > 2 else ''
            session.add(PlanEntry(datum=datum, messdiener_text=mess, art_uhrzeit=art))
        session.commit()
    finally:
        session.close()

# CSV einlesen
def load_plan():
    try:
        with open('data/plan.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            return list(reader)
    except FileNotFoundError:
        # Erstelle eine Standard-CSV-Datei falls sie nicht existiert
        default_plan = [
            ['Datum', 'Messdiener', 'Art/Uhrzeit'],
            ['27.07.2024', '', 'Gottesdienst 10:00'],
            ['03.08.2024', '', ''],
            ['10.08.2024', '', '']
        ]
        save_plan(default_plan)
        return default_plan

# CSV speichern
def save_plan(plan):
    with open('data/plan.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(plan)

# Warteschlangen (Queues) Datenzugriff
QUEUES_FILE = 'data/queues.csv'
ENROLLMENTS_FILE = 'data/enrollments.csv'


def load_queues():
    try:
        with open(QUEUES_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            if not rows:
                raise FileNotFoundError
            return rows
    except FileNotFoundError:
        default = [['ID', 'Name']]
        save_queues(default)
        return default


def save_queues(rows):
    with open(QUEUES_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def load_enrollments():
    try:
        with open(ENROLLMENTS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            if not rows:
                raise FileNotFoundError
            return rows
    except FileNotFoundError:
        default = [['Person', 'QueueID', 'Timestamp']]
        save_enrollments(default)
        return default


def save_enrollments(rows):
    with open(ENROLLMENTS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def next_queue_id(queues):
    # queues: list of rows including header ['ID','Name']
    if len(queues) <= 1:
        return '1'
    try:
        max_id = max(int(row[0]) for row in queues[1:] if row and row[0].isdigit())
        return str(max_id + 1)
    except ValueError:
        return str(len(queues))


def count_user_enrollments(enrollments, person):
    # count unique queues a person is enrolled in
    if len(enrollments) <= 1:
        return 0
    queue_ids = set()
    for row in enrollments[1:]:
        if len(row) >= 2 and row[0].strip().lower() == person.strip().lower():
            queue_ids.add(row[1])
    return len(queue_ids)


@app.route('/queues', methods=['GET'])
def queues_view():
    session = SessionLocal()
    try:
        q_list = session.query(Queue).order_by(Queue.id.asc()).all()
        e_list = session.query(Enrollment).order_by(Enrollment.id.asc()).all()
        # CSV-ähnliche Struktur für bestehende Templates
        queues = [['ID', 'Name']]
        for q in q_list:
            queues.append([str(q.id), q.name])
        enroll_by_queue = {}
        for e in e_list:
            qid = str(e.queue_id)
            enroll_by_queue.setdefault(qid, []).append(e.person)
        return render_template('queues.html', queues=queues, enroll_by_queue=enroll_by_queue)
    finally:
        session.close()


@app.route('/queues/enroll', methods=['POST'])
def queues_enroll():
    name = request.form.get('name', '').strip()
    qid = request.form.get('queue_id', '').strip()
    if not name or not qid:
        flash('Name und gültige Warteschlange erforderlich.', 'error')
        return redirect(url_for('queues_view'))

    session = SessionLocal()
    try:
        # Queue validieren
        q = session.query(Queue).filter_by(id=int(qid)).one_or_none()
        if not q:
            flash('Ungültige Warteschlange.', 'error')
            return redirect(url_for('queues_view'))

        # Limit prüfen: max 2 unterschiedliche Queues
        from sqlalchemy import func
        unique_count = session.query(func.count(func.distinct(Enrollment.queue_id))).filter(Enrollment.person.ilike(name)).scalar()
        if unique_count is None:
            unique_count = 0

        # Duplikat in derselben Queue?
        exists = session.query(Enrollment).filter_by(person=name, queue_id=q.id).first()
        if exists:
            flash('Du bist bereits in dieser Warteschlange eingetragen.', 'info')
            return redirect(url_for('queues_view'))

        if unique_count >= 2:
            flash('Maximal 2 Warteschlangen pro Person erlaubt.', 'error')
            return redirect(url_for('queues_view'))

        # Eintragen
        timestamp = datetime.now().isoformat(timespec='minutes')
        session.add(Enrollment(person=name, queue_id=q.id, timestamp=timestamp))
        session.commit()
        flash('Erfolgreich eingetragen!', 'success')
        return redirect(url_for('queues_view'))
    finally:
        session.close()


@app.route('/admin/queues', methods=['GET', 'POST'])
def admin_queues():
    if not session.get('admin'):
        flash('Sie müssen sich als Administrator anmelden!', 'error')
        return redirect(url_for('login'))

    session = SessionLocal()

    if request.method == 'POST':
        if 'add_queue' in request.form:
            name = request.form.get('queue_name', '').strip()
            if not name:
                flash('Name der Warteschlange darf nicht leer sein.', 'error')
                return redirect(url_for('admin_queues'))
            session.add(Queue(name=name))
            session.commit()
            flash('Warteschlange hinzugefügt.', 'success')
            return redirect(url_for('admin_queues'))

        if 'delete_queue' in request.form:
            qid = request.form.get('queue_id', '').strip()
            try:
                qid_int = int(qid)
            except Exception:
                flash('Ungültige Queue-ID.', 'error')
                return redirect(url_for('admin_queues'))
            # Enrollments werden per FK-Constraint entfernt, aber zur Sicherheit explizit löschen
            session.query(Enrollment).filter(Enrollment.queue_id == qid_int).delete()
            session.query(Queue).filter(Queue.id == qid_int).delete()
            session.commit()
            flash('Warteschlange gelöscht.', 'info')
            return redirect(url_for('admin_queues'))


        if 'clear_enrollments' in request.form:
            qid = request.form.get('queue_id', '').strip()
            try:
                qid_int = int(qid)
            except Exception:
                flash('Ungültige Queue-ID.', 'error')
                return redirect(url_for('admin_queues'))
            session.query(Enrollment).filter(Enrollment.queue_id == qid_int).delete()
            session.commit()
            flash('Einträge der Warteschlange geleert.', 'info')
            return redirect(url_for('admin_queues'))


    # Für Anzeige vorbereiten
    q_list = session.query(Queue).order_by(Queue.id.asc()).all()
    e_list = session.query(Enrollment).order_by(Enrollment.id.asc()).all()
    queues = [['ID', 'Name']]
    for q in q_list:
        queues.append([str(q.id), q.name])
    enroll_by_queue = {}
    for e in e_list:
        qid = str(e.queue_id)
        enroll_by_queue.setdefault(qid, []).append(e.person)

    session.close()
    return render_template('admin_queues.html', queues=queues, enroll_by_queue=enroll_by_queue)

@app.route('/')
def index():
    plan = get_plan_list()
    return render_template('index.html', plan=plan)

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            password = request.form.get('password', '')
            logger.info(f"Login-Versuch mit Passwort-Länge: {len(password) if password else 0}")

            if password == ADMIN_PASSWORD:
                session['admin'] = True
                flash('Erfolgreich als Administrator angemeldet!', 'success')
                logger.info("Erfolgreiche Admin-Anmeldung")
                return redirect(url_for('edit'))
            else:
                flash('Falsches Passwort!', 'error')
                logger.warning("Fehlgeschlagener Login-Versuch")

        return render_template('login.html')

    except Exception as e:
        logger.error(f"Fehler in login(): {e}")
        flash('Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.', 'error')
        return render_template('login.html')

@app.route('/edit', methods=['GET', 'POST'])
def edit():
    if not session.get('admin'):
        flash('Sie müssen sich als Administrator anmelden!', 'error')
        return redirect(url_for('login'))

    plan = get_plan_list()
    if request.method == 'POST':
        # Neue Zeile hinzufügen
        if 'add_row' in request.form:
            # Stelle sicher, dass die neue Zeile die aktuelle Spaltenanzahl hat
            expected_cols = len(plan[0]) if plan and len(plan) > 0 else 3
            plan.append([''] * expected_cols)
            save_plan_db(plan)
            flash('Neue Zeile hinzugefügt!', 'success')
            return redirect(url_for('edit'))

        # Plan speichern
        if 'save_plan' in request.form:
            new_plan = []
            # Header setzen (mit neuer Spalte Art/Uhrzeit)
            new_plan.append(['Datum', 'Messdiener', 'Art/Uhrzeit'])

            # Datenzeilen verarbeiten
            row_count = int(request.form.get('row_count', 0))
            for i in range(1, row_count + 1):
                datum = request.form.get(f'datum_{i}', '').strip()
                messdiener_text = request.form.get(f'messdiener_{i}', '').strip()
                art_zeit = request.form.get(f'art_zeit_{i}', '').strip()
                if datum or messdiener_text or art_zeit:  # Nur speichern wenn mindestens ein Feld ausgefüllt
                    new_plan.append([datum, messdiener_text, art_zeit])

            save_plan_db(new_plan)
            flash('Plan erfolgreich gespeichert!', 'success')
            return redirect(url_for('index'))

    return render_template('edit.html', plan=plan)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Erfolgreich abgemeldet!', 'info')
    return redirect(url_for('index'))

@app.route('/debug-env')
def debug_env():
    """Debug-Route um Umgebungsvariablen zu überprüfen (nur für Entwicklung)"""
    if os.environ.get('FLASK_ENV') == 'development':
        env_info = {
            'SECRET_KEY_SET': bool(os.environ.get('SECRET_KEY')),
            'ADMIN_PASSWORD_SET': bool(os.environ.get('ADMIN_PASSWORD')),
            'PORT': os.environ.get('PORT', 'nicht gesetzt'),
            'FLASK_ENV': os.environ.get('FLASK_ENV', 'nicht gesetzt'),
        }
        return f"<pre>{env_info}</pre>"
    else:
        return "Debug-Info nur in Entwicklung verfügbar", 403

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starte Server auf Port: {port}")
        logger.info(f"Debug-Modus: {os.environ.get('FLASK_ENV') == 'development'}")

        # Debug-Modus nur in Entwicklung
        debug_mode = os.environ.get('FLASK_ENV') == 'development'
        app.run(host='0.0.0.0', port=port, debug=debug_mode)

    except Exception as e:
        logger.error(f"Fehler beim Starten des Servers: {e}")
        # Fallback ohne Port-Parsing
        app.run(host='0.0.0.0', port=5000, debug=False)
