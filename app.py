from flask import Flask, render_template, request, redirect, url_for, session, flash
import csv
import os
from datetime import datetime

app = Flask(__name__)
# Sicherheit: Secret Key und Admin-Passwort aus Umgebungsvariablen
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-nur-fuer-lokale-entwicklung')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'adminpass')

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
            ['Datum', 'Messdiener'],
            ['27.07.2024', 'Finni, Lukas, Isabella'],
            ['03.08.2024', ''],
            ['10.08.2024', '']
        ]
        save_plan(default_plan)
        return default_plan

# CSV speichern
def save_plan(plan):
    with open('data/plan.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(plan)

@app.route('/')
def index():
    plan = load_plan()
    return render_template('index.html', plan=plan)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        if password == ADMIN_PASSWORD:
            session['admin'] = True
            flash('Erfolgreich als Administrator angemeldet!', 'success')
            return redirect(url_for('edit'))
        else:
            flash('Falsches Passwort!', 'error')
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
            plan.append(['', '', '', ''])
            save_plan(plan)
            flash('Neue Zeile hinzugefügt!', 'success')
            return redirect(url_for('edit'))

        # Plan speichern
        if 'save_plan' in request.form:
            new_plan = []
            # Header setzen
            new_plan.append(['Datum', 'Messdiener'])

            # Datenzeilen verarbeiten
            row_count = int(request.form.get('row_count', 0))
            for i in range(1, row_count + 1):
                datum = request.form.get(f'datum_{i}', '').strip()
                messdiener_text = request.form.get(f'messdiener_{i}', '').strip()
                if datum or messdiener_text:  # Nur speichern wenn mindestens ein Feld ausgefüllt
                    new_plan.append([datum, messdiener_text])

            save_plan(new_plan)
            flash('Plan erfolgreich gespeichert!', 'success')
            return redirect(url_for('index'))

    return render_template('edit.html', plan=plan)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Erfolgreich abgemeldet!', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
