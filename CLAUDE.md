# CLAUDE.md - Hermine-Mediatool

## Project Overview
Hermine-Mediatool is a media downloader and web UI for the Hermine/THW Messenger platform (Stashcat-based). It automatically downloads images and videos from configured channels, processes EXIF metadata, and uploads files to Nextcloud via WebDAV.

## Architecture

### Services (Docker Compose at `~/thw/hermine-fotos/docker-compose.yml`)
- **hermine-downloader**: One-shot Python job (`python3 -m src.main`), runs periodically via cron/manual
- **hermine-web**: FastAPI web UI on port 8888, `restart: unless-stopped`

Both build from `./Hermine-Mediatool` with `UID=1001 GID=1001` (matches host `dockeruser`).
The downloader uses `network_mode: host` (required - Docker bridge networking breaks outbound uploads on this host).

### Source Layout (`src/`)
```
src/
├── main.py              # Entry point: retry uploads → process channels → stats
├── config.py            # Config from .env (HermineConfig, NextcloudConfig, etc.)
├── logger.py            # Logging setup
├── api/
│   ├── hermine_client.py   # Hermine/Stashcat API (auth, download, decryption)
│   ├── nextcloud_client.py # WebDAV upload with retry + verification
│   ├── models.py           # Pydantic models
│   └── exceptions.py
├── downloader/
│   ├── engine.py           # Core orchestration (download, upload, retry)
│   └── exif_processor.py
├── storage/
│   ├── database.py         # ManifestDB (SQLite)
│   ├── metadata_db.py      # Extended image/video metadata tables
│   ├── path_builder.py     # Template-based path construction
│   └── exif_handler.py
├── crypto/
│   └── decryption.py       # RSA/AES decryption for encrypted channels
├── cli/
│   └── commands.py         # Click CLI (list-channels, stats, etc.)
└── web/
    ├── app.py              # FastAPI (stats API, file listing, static files)
    ├── static/
    └── templates/
```

### Data Flow
1. Hermine API → download encrypted file → decrypt (RSA/AES) → save locally
2. Process EXIF (set author, sanitize) → validate (min 10KB, PIL verify for images)
3. Upload to Nextcloud via WebDAV (with size verification) → delete local if configured
4. All tracked in SQLite manifest DB with status: `completed`, `corrupted`, `upload_pending`, `upload_failed`

### Execution Order in main.py
1. `redownload_corrupted_files()` - clean up corrupted files
2. `retry_pending_uploads()` - retry files with upload_pending/upload_failed
3. `process_channel()` for each target channel - download new files
4. If Nextcloud reconnected: `retry_pending_uploads()` again

## Key Technical Details

### webdav4 Library
- `upload_fileobj()` defaults to `overwrite=False` - **must pass `overwrite=True`**
- `client.info(path)` returns dict with `content_length` key
- `client.remove(path)` deletes files

### NextcloudClient Behavior
- `__init__` does NOT raise on connection failure - stores `_connected=False`
- `is_connected` property checks state; `reconnect()` retries connection
- Upload uses `asyncio.to_thread()` to wrap sync webdav4 calls

### Database
- SQLite at `data/manifest.db`
- `file_exists()` only returns True for `status='completed'`
- `get_files_needing_upload()` must NOT filter `local_path IS NOT NULL`
- Status transitions: download → completed/upload_pending/upload_failed/corrupted

### Docker Networking
- **CRITICAL**: The downloader MUST use `network_mode: host`. Docker bridge networking on this host silently breaks outbound TCP data transfers (uploads). PROPFIND/small requests work fine, but PUT with >10KB payload causes write timeouts or server disconnects. This was diagnosed Feb 2026 and is a host-level Docker bridge issue, not a code bug.

## Configuration
- `.env` at project root (NOT in git), mounted read-only into container
- Key settings: `NEXTCLOUD_ENABLED`, `DELETE_LOCAL_AFTER_UPLOAD`, `TARGET_CHANNELS`, `PATH_TEMPLATE`
- `PATH_TEMPLATE` default: `{year}/{month:02d}/{sender}_{filename}`

## Build & Run
```bash
# From ~/thw/hermine-fotos/
docker compose build hermine-downloader
docker compose up hermine-downloader        # Run once (foreground)
docker compose up -d hermine-web            # Start web UI
```

## Known Issues
- EXIF author setting fails on some images: `"dump" got wrong type of exif value` - non-blocking, file still uploads
- `retry_pending_uploads` + `DELETE_LOCAL_AFTER_UPLOAD=true` race condition: if a file is re-downloaded and uploaded during channel processing, the retry step may find the old DB record but local file is gone. Resolves on subsequent runs.
- Some files only return thumbnails from Hermine API (< 10KB) - retried up to 10 times with backoff

## Git
- Repo: `Hermine-Mediatool/`, branch `main`
- Remote has PAT token in URL (HHerrgesell account)
- Git user: Henry <github@hherrgesell.de>
- `docker-compose.yml` and `.env` are NOT in the git repo
