# Hermine Media Downloader 🎬

Automatisiertes Skript zum vollständigen Download aller Bilder und Videos aus Hermine-Kanälen (THW Messenger) mit erweiterten Konfigurationsoptionen.

## Features

✨ **Kern-Features:**
- Automatischer Download aller Mediendateien aus Hermine-Kanälen
- Intelligente Duplikat-Erkennung basierend auf SHA256-Hash
- Konfigurierbare Ordnerstruktur mit Templating
- Automatische Metadaten-Extraktion (Autor/Sender)
- Fehlertolerante Implementierung mit Exponential-Backoff Retry-Logik
- SQLite-Manifest für Download-Tracking und Statistiken
- Asynchrone/parallele Downloads für optimale Performance
- **Unterstützung für verschlüsselte Kanäle** mit RSA-Entschlüsselung

🔗 **Integration:**
- Hermine/Stashcat API-Support (flexibel konfigurierbar)
- Optional: Nextcloud WebDAV Auto-Upload
- Strukturierte Logging-Ausgabe

🛠️ **Developer-Features:**
- CLI-Tools zur Konfigurationshilfe (Kanal-/Absender-Listings)
- Umfangreiche Error-Handling und Retry-Strategien
- Konfigurierbare Pfad-Templates
- MIME-Type Filterung
- **Vollständig konfigurierbare Domains und API-Settings**

## Installation

### Anforderungen
- Python 3.9+
- pip
- Git

### Setup

```bash
# 1. Repository klonen
git clone https://github.com/HHerrgesell/Hermine-Mediatool.git
cd Hermine-Mediatool

# 2. Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Konfiguration erstellen
cp .env.example .env
# Bearbeite .env mit deinen Zugangsdaten

# 5. Hilfsprogramme testen
python3 -m src.cli list-channels      # Zeige verfügbare Kanäle
python3 -m src.cli list-senders CHANNEL_ID  # Zeige Absender

# 6. Starten
python3 -m src.main
```

## Konfiguration

### .env Konfiguration

Kopiere `.env.example` zu `.env` und konfiguriere:

```bash
# Hermine Zugangsdaten
HERMINE_BASE_URL=https://hermine.example.com
HERMINE_USERNAME=your_username
HERMINE_PASSWORD=your_password

# Zielkanäle (komma-separiert)
TARGET_CHANNELS=channel_id_1,channel_id_2,channel_id_3

# Download-Verzeichnis
DOWNLOAD_DIR=./downloads

# Pfad-Template für Dateiorganisation
PATH_TEMPLATE={year}/{month:02d}/{sender}_{filename}

# Performance
MAX_CONCURRENT_DOWNLOADS=5
RETRY_ATTEMPTS=3

# Logging
LOG_LEVEL=INFO
```

### Verschlüsselte Kanäle

Für verschlüsselte Hermine-Kanäle wird ein RSA-Schlüssel benötigt:

```bash
HERMINE_ENCRYPTION_KEY=your_rsa_passphrase
```

Dieser Schlüssel wird verwendet, um verschlüsselte Medien-Dateien zu entschlüsseln. Das Crypto-Modul behandelt die RSA-Entschlüsselung automatisch, wenn verschlüsselte Dateien erkannt werden.

### Erweiterte API-Konfiguration

Für andere Hermine/Stashcat-Installationen können die Domain-Einstellungen angepasst werden:

```bash
# Domains (optional - Defaults für THW Messenger)
HERMINE_APP_DOMAIN=https://app.thw-messenger.de
HERMINE_FILE_DOMAIN=https://app.thw-messenger.de/thw/app.thw-messenger.de

# API Client Settings (optional - imitiert Browser-Verhalten)
HERMINE_USER_AGENT=Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N)...
HERMINE_APP_NAME=hermine@thw-Chrome:97.0.4692.99-browser-4.11.1
```

| Parameter | Beschreibung | Default |
|-----------|--------------|--------|
| `HERMINE_APP_DOMAIN` | Domain für Origin/Referer Headers | `https://app.thw-messenger.de` |
| `HERMINE_FILE_DOMAIN` | Domain-Pattern für Datei-Downloads | `https://app.thw-messenger.de/thw/app.thw-messenger.de` |
| `HERMINE_USER_AGENT` | User-Agent String für Requests | Chrome Mobile UA |
| `HERMINE_APP_NAME` | App-Identifier für Authentifizierung | `hermine@thw-Chrome:...` |

> **Hinweis:** Diese Einstellungen sind optional. Die Defaults sind für den THW Messenger konfiguriert und funktionieren ohne Änderungen.

### Pfad-Templates

Standard-Template: `{year}/{month:02d}/{sender}_{filename}`

Verfügbare Platzhalter:
- `{year}` - Jahreszahl (YYYY)
- `{month:02d}` - Monatszahl (01-12)
- `{day:02d}` - Tagesszahl (01-31)
- `{sender}` - Absender-Name (gekürzt)
- `{filename}` - Original-Dateiname
- `{channel_name}` - Kanal-Name

Beispiele:
```
{year}/{month:02d}/{sender}_{filename}       # 2026/01/Max_Mustermann_photo.jpg
{channel_name}/{year}/{month:02d}/{filename} # Einsätze/2026/01/photo.jpg
{sender}/{year}/{filename}                   # Max_Mustermann/2026/photo.jpg
```

## Verwendung

### CLI-Befehle - Vollständige Liste

```bash
# 1. Kanäle auflisten
python3 -m src.cli list-channels

# 2. Absender in einem Kanal anzeigen
python3 -m src.cli list-senders CHANNEL_ID

# 3. Download-Statistiken anzeigen
python3 -m src.cli stats [--channel CHANNEL_ID]

# 4. Pfad-Template Hilfe anzeigen
python3 -m src.cli show-template-help
```

### Kanal-IDs finden

```bash
python3 -m src.cli list-channels
```

Ausgabe:
```
📋 Verfügbare Kanäle:

  1. Einsätze
     ID: einsaetze_001
     Mitglieder: 42
  ...
```

### Absender in Kanal anzeigen

```bash
python3 -m src.cli list-senders einsaetze_001
```

Ausgabe:
```
👥 Absender im Kanal einsaetze_001:

  1. Max Mustermann
     ID: user_123
     Nachrichten: 156
  ...
```

### Statistiken anzeigen

```bash
python3 -m src.cli stats
```

Ausgabe:
```
📊 Download-Statistiken:

  Dateien gesamt:    4521
  Größe:             2345.67 MB
  Kanäle:            3
  Absender:          18
  Fehler:            2

  Nach Kanal:
    einsaetze_001: 2341 Dateien
    ...
```

### Pfad-Template Hilfe

```bash
python3 -m src.cli show-template-help
```

Zeigt detaillierte Informationen über verfügbare Template-Platzhalter und Formatierungsoptionen.

### Einfacher Download aller konfigurierter Kanäle

```bash
python3 -m src.main
```

Ausgabe:
```
======================================================================
🚀 Hermine Media Downloader startet...
======================================================================
🔗 Verbinde zu https://hermine.example.com...
✓ Hermine API Authentication successful

======================================================================
🎯 Verarbeite Kanal: einsaetze_001
======================================================================
  Nachrichten gelesen: 100...
  Nachrichten gelesen: 200...
  ...
✓ Heruntergeladen: photo_001.jpg (2.34 MB)
✓ Heruntergeladen: video_002.mp4 (145.67 MB)
...
```

## Docker

### Mit Docker Compose

```bash
# Konfiguration vorbereiten
cp .env.example .env
# Bearbeite .env

# Starten
docker-compose up

# Im Hintergrund
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Stoppen
docker-compose down
```

### Manueller Docker Build

```bash
# Build
docker build -t hermine-downloader .

# Run
docker run -v $(pwd)/.env:/.env \
           -v $(pwd)/downloads:/app/downloads \
           hermine-downloader
```

## Features im Detail

### Intelligente Duplikat-Erkennung

Das Skript erkennt Duplikate auf zwei Ebenen:

1. **File-ID basiert:** Verhindert erneutes Herunterladen derselben Datei
2. **Hash-basiert (SHA256):** Erkennt identische Inhalte, auch wenn sie neue IDs haben

```bash
CALCULATE_CHECKSUMS=true  # Aktiviert Hash-Berechnung
```

### Fehlertoleranz

- Automatische Retry-Logik mit exponentiellem Backoff
- Timeout-Handling für große Dateien
- Graceful Degradation bei API-Fehlern
- Detailliertes Error-Logging

```bash
RETRY_ATTEMPTS=3          # Anzahl Wiederholungsversuche
RETRY_DELAY=1.0           # Initiale Verzögerung (Sekunden)
RETRY_BACKOFF=2.0         # Backoff-Multiplikator
DOWNLOAD_TIMEOUT=60       # Timeout pro Datei (Sekunden)
```

### Parallele Downloads

```bash
MAX_CONCURRENT_DOWNLOADS=5  # Anzahl paralleler Downloads
CHUNK_SIZE=8388608          # Chunk-Größe (8MB default)
```

### Metadaten-Extraktion

- Sender/Autor wird automatisch im Dateinamen eingebettet
- Original-Timestamp wird beibehalten
- SQLite-Manifest speichert vollständige Metadaten

### Nextcloud Integration

Optionale automatische Uploads zu Nextcloud:

```bash
NEXTCLOUD_ENABLED=true
NEXTCLOUD_AUTO_UPLOAD=true
DELETE_LOCAL_AFTER_UPLOAD=true  # Optional: Lösche lokal nach Upload
```

## Troubleshooting

### API-Authentifizierung fehlgeschlagen

```
Überprüfe:
- HERMINE_BASE_URL korrekt?
- Benutzername/Passwort korrekt?
- Netzwerk-Konnektivität?
```

Debugging:
```bash
LOG_LEVEL=DEBUG python3 -m src.main
```

### Kanal-IDs finden

```bash
python3 -m src.cli list-channels
```

### Performance optimieren

```bash
MAX_CONCURRENT_DOWNLOADS=10  # Erhöhe Parallelisierung
CHUNK_SIZE=16777216          # Vergrößere Chunks (16MB)
```

### SSL-Fehler

Für selbstsignierte Zertifikate:
```bash
HERMINE_VERIFY_SSL=false
```

### Speicherplatz vollgelaufen

Nutze Nextcloud Auto-Upload und Löschen:
```bash
NEXTCLOUD_AUTO_UPLOAD=true
DELETE_LOCAL_AFTER_UPLOAD=true
```

### Verschlüsselte Dateien können nicht entschlüsselt werden

Stelle sicher, dass der ENCRYPTION_KEY korrekt konfiguriert ist:
```bash
HERMINE_ENCRYPTION_KEY=your_rsa_passphrase
```

### Andere Hermine/Stashcat Installation

Für andere Installationen (nicht THW Messenger) passe die Domains an:
```bash
HERMINE_APP_DOMAIN=https://your-instance.example.com
HERMINE_FILE_DOMAIN=https://files.your-instance.example.com
```

## Projektstruktur

```
Hermine-Mediatool/
├── src/
│   ├── __init__.py
│   ├── config.py              # Konfigurationsmanagement
│   ├── logger.py              # Logging-Setup
│   ├── main.py                # Haupteinstiegspunkt
│   ├── api/
│   │   ├── __init__.py
│   │   ├── models.py             # Datenmodelle
│   │   ├── hermine_client.py     # Hermine API Client
│   │   ├── nextcloud_client.py   # Nextcloud WebDAV Client
│   │   └── exceptions.py         # Custom Exceptions
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py           # CLI-Befehle
│   ├── crypto/
│   │   ├── __init__.py
│   │   └── encryption.py         # RSA-Entschlüsselung
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py           # SQLite Manifest
│   │   └── path_builder.py       # Pfad-Konstruktion
│   └── downloader/
│       ├── __init__.py
│       └── engine.py             # Download-Engine
├── .env.example            # Konfigurationsvorlage
├── requirements.txt        # Python-Dependencies
├── Dockerfile              # Docker-Image
├── docker-compose.yml      # Docker Compose
├── .gitignore              # Git-Ignore
└── README.md               # Diese Datei
```

## Lizenz

MIT License - siehe LICENSE für Details

## Beitragen

Contributions sind willkommen! Bitte erstelle einen Issue oder Pull Request.

### Entwicklung

```bash
# Virtuelle Umgebung aktivieren
source venv/bin/activate

# Code formatieren
black src/

# Linting
flake8 src/

# Type Checking
mypy src/

# Tests
pytest tests/
```

## Support

Für Bugs und Fragen: [Issues](https://github.com/HHerrgesell/Hermine-Mediatool/issues)

---

**Version:** 1.3.1  
**Zuletzt aktualisiert:** 2026-05-02  
**Status:** Production Ready (Rolling Release) ✅
