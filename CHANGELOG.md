# Changelog

Alle bemerkenswerten Änderungen dieses Projekts werden in dieser Datei dokumentiert.

## [1.1.0] - 2026-01-16

### Hinzugefügt
- Intelligente Duplikat-Erkennung (File-ID + SHA256-Hash)
- Parallele/asynchrone Downloads mit konfigurierbarer Concurrency
- SQLite-Manifest für Download-Tracking und Statistiken
- Konfigurierbare Pfad-Templates mit Platzhaltern
- Nextcloud WebDAV Auto-Upload Integration
- CLI-Tools: list-channels, list-senders, stats, show-template-help
- Exponential-Backoff Retry-Logik mit Fehlerlogging
- Docker- und Docker Compose-Unterstützung
- Umfangreiche Dokumentation (README, INSTALL, Makefile)

### Verbesserungen
- Robustes Error-Handling und Graceful Degradation
- Memory-effiziente Chunk-basierte Downloads
- Metadata-Extraktion (Sender, Timestamps)
- Strukturierte Logging-Ausgabe mit Farbcodierung
- MIME-Type Filterung und Dateisize-Limits
- SSL-Verifikation optional

### Sicherheit
- Environment-Variable basierte Konfiguration (keine hartcodierten Credentials)
- Sichere Dateioperationen mit Sanitization
- Validierung von Eingaben

## [1.0.0] - 2026-01-01

### Hinzugefügt
- Initial Release
- Basis Download-Funktionalität
- Hermine API Client
- Konfigurationsmanagement
