# Messdienerplan - Webbasierte Verwaltung

Eine einfache, webbasierte Anwendung zur Verwaltung eines Messdienerplans mit Python Flask.

## Features

- **Öffentliche Ansicht**: Jeder kann den aktuellen Messdienerplan einsehen
- **Admin-Bereich**: Geschützter Bereich zur Bearbeitung des Plans
- **CSV-Datenspeicher**: Einfache Datenhaltung in CSV-Format
- **Responsive Design**: Bootstrap-basierte Benutzeroberfläche
- **Deployment-ready**: Vorbereitet für kostenloses Hosting

## Installation und lokale Entwicklung

### Voraussetzungen
- Python 3.11 oder höher
- pip (Python Package Manager)

### Setup
1. Repository klonen oder herunterladen
2. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
3. **Umgebungsvariablen einrichten** (wichtig für Sicherheit):
   ```bash
   # .env.example zu .env kopieren
   cp .env.example .env

   # .env bearbeiten und eigene Werte setzen:
   # SECRET_KEY=ihr-geheimer-schluessel
   # ADMIN_PASSWORD=ihr-sicheres-passwort
   ```
4. Anwendung starten:
   ```bash
   python app.py
   ```
5. Browser öffnen: `http://localhost:5000`

## Verwendung

### Öffentliche Ansicht
- Besuchen Sie die Hauptseite, um den aktuellen Messdienerplan zu sehen
- Der Plan zeigt Datum und zugeteilte Messdiener in einer übersichtlichen Tabelle

### Administrator-Bereich
- Klicken Sie auf das Schlüssel-Symbol oder besuchen Sie `/login`
- **Passwort**: Wird über Umgebungsvariable `ADMIN_PASSWORD` gesetzt
- **Lokal**: Standard ist `adminpass` (nur für Entwicklung!)
- Im Admin-Bereich können Sie:
  - Neue Zeilen hinzufügen
  - Bestehende Einträge bearbeiten
  - Beliebig viele Messdiener pro Tag eintragen
  - Den Plan speichern

## Deployment

### Render.com (Empfohlen)
1. Repository auf GitHub hochladen
2. Render.com Account erstellen
3. "New Web Service" erstellen und GitHub Repository verbinden
4. Render erkennt automatisch die `render.yaml` Konfiguration
5. Deploy starten

### Heroku
1. Repository auf GitHub hochladen
2. Heroku Account erstellen
3. Neue App erstellen und GitHub Repository verbinden
4. Automatisches Deployment aktivieren

### Railway
1. Repository auf GitHub hochladen
2. Railway Account erstellen
3. "Deploy from GitHub" wählen
4. Repository auswählen und deployen

## Konfiguration

### Sicherheit
**Wichtig**: Ändern Sie das Admin-Passwort vor dem Deployment!

In `app.py` Zeile 28:
```python
if password == 'adminpass':  # HIER ÄNDERN!
```

### Umgebungsvariablen (für Produktion)
- `FLASK_ENV=production`
- `SECRET_KEY=ihr-geheimer-schluessel`
- `ADMIN_PASSWORD=ihr-admin-passwort`

## Dateistruktur

```
messdienerplan/
├── app.py              # Hauptanwendung
├── requirements.txt    # Python-Abhängigkeiten
├── render.yaml        # Render.com Konfiguration
├── Procfile           # Heroku Konfiguration
├── runtime.txt        # Python Version
├── data/
│   └── plan.csv       # Messdienerplan-Daten
└── templates/
    ├── index.html     # Hauptseite
    ├── login.html     # Login-Seite
    └── edit.html      # Bearbeitungsseite
```

## Technische Details

- **Framework**: Flask 3.1.1
- **Frontend**: Bootstrap 5.3.0 + Bootstrap Icons
- **Datenspeicher**: CSV-Dateien
- **Session-Management**: Flask Sessions
- **Responsive Design**: Mobile-first Ansatz

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.

## Support

Bei Fragen oder Problemen erstellen Sie bitte ein Issue im GitHub Repository.
