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
            ['27.07.2024', 'Finni, Lukas, Isabella', 'Gottesdienst 10:00'],
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
    queues = load_queues()
    enrollments = load_enrollments()
    # Map enrollments by QueueID
    enroll_by_queue = {}
    for row in enrollments[1:]:
        if len(row) >= 2:
            qid = row[1]
            enroll_by_queue.setdefault(qid, []).append(row[0])
    return render_template('queues.html', queues=queues, enroll_by_queue=enroll_by_queue)


@app.route('/queues/enroll', methods=['POST'])
def queues_enroll():
    name = request.form.get('name', '').strip()
    qid = request.form.get('queue_id', '').strip()
    if not name or not qid:
        flash('Name und gültige Warteschlange erforderlich.', 'error')
        return redirect(url_for('queues_view'))

    queues = load_queues()
    valid_ids = {row[0] for row in queues[1:] if row and len(row) >= 1}
    if qid not in valid_ids:
        flash('Ungültige Warteschlange.', 'error')
        return redirect(url_for('queues_view'))

    enrollments = load_enrollments()
    # Prüfe, ob Nutzer bereits 2 unterschiedlichen Warteschlangen beigetreten ist
    current_unique = count_user_enrollments(enrollments, name)

    # Prüfe Duplikat in derselben Queue
    already_in_queue = any((len(row) >= 2 and row[0].strip().lower() == name.lower() and row[1] == qid) for row in enrollments[1:])
    if already_in_queue:
        flash('Du bist bereits in dieser Warteschlange eingetragen.', 'info')
        return redirect(url_for('queues_view'))

    if current_unique >= 2:
        flash('Maximal 2 Warteschlangen pro Person erlaubt.', 'error')
        return redirect(url_for('queues_view'))

    # Eintragen
    timestamp = datetime.now().isoformat(timespec='minutes')
    enrollments.append([name, qid, timestamp])
    save_enrollments(enrollments)
    flash('Erfolgreich eingetragen!', 'success')
    return redirect(url_for('queues_view'))


@app.route('/admin/queues', methods=['GET', 'POST'])
def admin_queues():
    if not session.get('admin'):
        flash('Sie müssen sich als Administrator anmelden!', 'error')
        return redirect(url_for('login'))

    queues = load_queues()

    if request.method == 'POST':
        if 'add_queue' in request.form:
            name = request.form.get('queue_name', '').strip()
            if not name:
                flash('Name der Warteschlange darf nicht leer sein.', 'error')
                return redirect(url_for('admin_queues'))
            qid = next_queue_id(queues)
            queues.append([qid, name])
            save_queues(queues)
            flash('Warteschlange hinzugefügt.', 'success')
            return redirect(url_for('admin_queues'))

        if 'delete_queue' in request.form:
            qid = request.form.get('queue_id', '').strip()
            queues = [queues[0]] + [row for row in queues[1:] if row[0] != qid]
            save_queues(queues)
            # Auch Anmeldungen für diese Queue entfernen
            enrollments = load_enrollments()
            enrollments = [enrollments[0]] + [row for row in enrollments[1:] if row[1] != qid]
            save_enrollments(enrollments)
            flash('Warteschlange gelöscht.', 'info')
            return redirect(url_for('admin_queues'))

        if 'clear_enrollments' in request.form:
            qid = request.form.get('queue_id', '').strip()
            enrollments = load_enrollments()
            enrollments = [enrollments[0]] + [row for row in enrollments[1:] if row[1] != qid]
            save_enrollments(enrollments)
            flash('Einträge der Warteschlange geleert.', 'info')
            return redirect(url_for('admin_queues'))

    # Für Anzeige: Enrollments pro Queue
    enrollments = load_enrollments()
    enroll_by_queue = {}
    for row in enrollments[1:]:
        if len(row) >= 2:
            qid = row[1]
            enroll_by_queue.setdefault(qid, []).append(row[0])

    return render_template('admin_queues.html', queues=queues, enroll_by_queue=enroll_by_queue)

@app.route('/')
def index():
    plan = load_plan()
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

    plan = load_plan()
    if request.method == 'POST':
        # Neue Zeile hinzufügen
        if 'add_row' in request.form:
            # Stelle sicher, dass die neue Zeile die aktuelle Spaltenanzahl hat
            expected_cols = len(plan[0]) if plan and len(plan) > 0 else 3
            plan.append([''] * expected_cols)
            save_plan(plan)
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

            save_plan(new_plan)
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
