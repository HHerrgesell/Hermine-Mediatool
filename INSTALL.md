# Installation Guide

## Systemanforderungen

- **Python:** 3.9 oder neuer
- **pip:** Paketmanager für Python
- **Git:** Für Repository-Klone
- **RAM:** Mindestens 512MB (abhängig von Download-Größe)
- **Festplatte:** Ausreichend Platz für Downloads

### Linux / macOS

```bash
# Python und pip überprüfen
python3 --version
pip3 --version

# Falls nicht installiert
# Ubuntu/Debian
sudo apt-get install python3 python3-pip python3-venv

# macOS (mit Homebrew)
brew install python3
```

### Windows

1. Python von [python.org](https://www.python.org/downloads/) herunterladen
2. Während Installation: Häckchen bei "Add Python to PATH" setzen
3. Command Prompt / PowerShell neu starten
4. Verifizieren:
   ```cmd
   python --version
   pip --version
   ```

## Installation

### 1. Repository klonen

```bash
git clone https://github.com/HHerrgesell/Hermine-Mediatool.git
cd Hermine-Mediatool
```

### 2. Virtuelle Umgebung erstellen

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Dependencies installieren

```bash
pip install -r requirements.txt
```

### 4. Konfiguration vorbereiten

```bash
cp .env.example .env
# Bearbeite .env mit deinen Zugangsdaten
```

### 5. Testen

```bash
# Kanale auflisten
python3 -m src.cli list-channels
```

Falls korrekt konfiguriert, sollte eine Liste der verfügbaren Kanäle erscheinen.

## Mit Docker

### Docker Installation

- Linux: [Get Docker](https://docs.docker.com/get-docker/)
- macOS: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop)

### Docker Compose Installation

Meist bereits mit Docker Desktop enthalten.

Falls nicht: `pip install docker-compose`

### Starten mit Docker

```bash
# .env erstellen
cp .env.example .env
# Bearbeite .env

# Mit Docker Compose starten
docker-compose up

# Im Hintergrund
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Stoppen
docker-compose down
```

## Troubleshooting

### "python: command not found"

Virtuelle Umgebung nicht aktiviert:
```bash
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate    # Windows
```

### "ModuleNotFoundError: No module named 'requests'"

Dependencies nicht installiert:
```bash
pip install -r requirements.txt
```

### "Permission denied"

Skript nicht ausführbar:
```bash
chmod +x src/main.py
```

### Import Errors

Stelle sicher, dass du im Projektverzeichnis bist:
```bash
cd Hermine-Mediatool
python3 -m src.main
```

## Next Steps

Nach erfolgreicher Installation:

1. [Konfiguration einrichten](README.md#konfiguration)
2. [Kanale auflisten](README.md#kanal-ids-finden)
3. [Downloader starten](README.md#einfacher-download-aller-konfigurierten-kanale)

## Hilfe

Bei Problemen:

- [GitHub Issues](https://github.com/HHerrgesell/Hermine-Mediatool/issues)
- [Troubleshooting Guide](README.md#troubleshooting)
