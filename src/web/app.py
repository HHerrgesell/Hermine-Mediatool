"""FastAPI Web Application for Hermine Mediatool."""
import os
import re
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from src.storage.database import ManifestDB

logger = logging.getLogger(__name__)

# Configuration from environment
DB_PATH = Path(os.getenv("DB_PATH", "data/manifest.db"))
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "downloads"))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))

# Database instance
db: Optional[ManifestDB] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global db
    logger.info(f"Starting Web UI - DB: {DB_PATH}")
    db = ManifestDB(DB_PATH)
    db.initialize()
    yield
    if db:
        db.close()
    logger.info("Web UI shutdown complete")


app = FastAPI(
    title="Hermine Mediatool",
    description="Web UI for managing downloaded media files",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local network - adjust if needed
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --- Pydantic Models for Validation ---

class FileIdParam(BaseModel):
    """Validated file ID parameter."""
    file_id: str = Field(..., min_length=1, max_length=100)

    @field_validator('file_id')
    @classmethod
    def validate_file_id(cls, v: str) -> str:
        """Validate file_id contains only safe characters."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Invalid file_id format')
        return v


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=25, ge=1, le=100)


class SearchParams(BaseModel):
    """Search/filter parameters."""
    search: Optional[str] = Field(default=None, max_length=100)
    channel_id: Optional[str] = Field(default=None, max_length=100)
    sender: Optional[str] = Field(default=None, max_length=100)

    @field_validator('search', 'channel_id', 'sender')
    @classmethod
    def sanitize_input(cls, v: Optional[str]) -> Optional[str]:
        """Sanitize input to prevent injection."""
        if v is None:
            return None
        # Remove any potentially dangerous characters
        sanitized = re.sub(r'[<>"\';&|`$]', '', v)
        return sanitized.strip() if sanitized else None


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    template_path = Path(__file__).parent / "templates" / "index.html"
    return FileResponse(template_path, media_type="text/html")


@app.get("/api/stats")
async def get_stats():
    """Get download statistics."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    stats = db.get_statistics()
    files_by_channel = db.get_files_by_channel()
    files_by_sender = db.get_files_by_sender()

    # Get top senders (limit to 10)
    top_senders = sorted(files_by_sender.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_files": stats.get("total_files", 0),
        "total_size_bytes": stats.get("total_size", 0),
        "total_size_formatted": format_bytes(stats.get("total_size", 0)),
        "channels": stats.get("channels", 0),
        "senders": stats.get("senders", 0),
        "errors": stats.get("errors", 0),
        "pending_uploads": stats.get("pending_uploads", 0),
        "corrupted_files": stats.get("corrupted_files", 0),
        "files_by_channel": files_by_channel,
        "top_senders": [{"name": s[0], "count": s[1]} for s in top_senders]
    }


@app.get("/api/files")
async def list_files(
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=25, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=100),
    channel_id: Optional[str] = Query(default=None, max_length=100),
    sender: Optional[str] = Query(default=None, max_length=100),
    status: Optional[str] = Query(default=None, max_length=20)
):
    """List all files with pagination and filtering."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Sanitize inputs
    params = SearchParams(search=search, channel_id=channel_id, sender=sender)
    # Validate status filter
    valid_statuses = {'completed', 'corrupted', 'upload_pending', 'upload_failed'}
    status_filter = status if status in valid_statuses else None

    offset = (page - 1) * per_page
    files = db.get_all_files(
        limit=per_page,
        offset=offset,
        search=params.search,
        channel_id=params.channel_id,
        sender=params.sender,
        status=status_filter
    )

    total = db.count_files(
        search=params.search,
        channel_id=params.channel_id,
        sender=params.sender,
        status=status_filter
    )

    # Format file data for frontend
    formatted_files = []
    for f in files:
        formatted_files.append({
            "id": f.get("id"),
            "file_id": f.get("file_id"),
            "filename": f.get("filename"),
            "mime_type": f.get("mime_type"),
            "file_size": f.get("file_size"),
            "file_size_formatted": format_bytes(f.get("file_size", 0)),
            "sender": f.get("sender"),
            "channel_id": f.get("channel_id"),
            "download_timestamp": f.get("download_timestamp"),
            "local_path": f.get("local_path"),
            "nextcloud_path": f.get("nextcloud_path"),
            "status": f.get("status", "completed"),
            "has_local_file": bool(f.get("local_path") and Path(f.get("local_path")).exists())
        })

    return {
        "files": formatted_files,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@app.get("/api/files/{file_id}")
async def get_file(file_id: str):
    """Get details for a specific file."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Validate file_id
    try:
        validated = FileIdParam(file_id=file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file = db.get_file_by_id(validated.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    local_path = file.get("local_path")
    has_local_file = bool(local_path and Path(local_path).exists())

    return {
        **file,
        "file_size_formatted": format_bytes(file.get("file_size", 0)),
        "has_local_file": has_local_file
    }


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str, delete_local: bool = Query(default=True)):
    """Delete a file from disk and optionally from database.

    Args:
        file_id: The file ID to delete
        delete_local: If True, delete the local file. If False, only remove from DB.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Validate file_id
    try:
        validated = FileIdParam(file_id=file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file = db.get_file_by_id(validated.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    local_deleted = False
    local_path = file.get("local_path")

    # Delete local file if requested and exists
    if delete_local and local_path:
        try:
            path = Path(local_path)
            if path.exists():
                # Security check: ensure path is within download directory
                if not is_safe_path(path, DOWNLOAD_DIR):
                    raise HTTPException(status_code=403, detail="Access denied")
                path.unlink()
                local_deleted = True
                logger.info(f"Deleted local file: {local_path}")
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete file")

    # Remove from database
    db_deleted = db.delete_file_record(validated.file_id)

    return {
        "success": True,
        "file_id": validated.file_id,
        "local_deleted": local_deleted,
        "db_deleted": db_deleted,
        "message": "File deleted successfully"
    }


@app.delete("/api/files/{file_id}/db-only")
async def remove_from_database(file_id: str):
    """Remove file from database only (triggers re-download on next sync).

    The local file is NOT deleted, only the database record.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Validate file_id
    try:
        validated = FileIdParam(file_id=file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file = db.get_file_by_id(validated.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found in database")

    # Remove from database only
    deleted = db.delete_file_record(validated.file_id)

    return {
        "success": deleted,
        "file_id": validated.file_id,
        "message": "Removed from database - file will be re-downloaded on next sync" if deleted else "Failed to remove from database"
    }


@app.post("/api/files/{file_id}/mark-corrupted")
async def mark_file_corrupted(file_id: str):
    """Mark a file as corrupted. Next downloader run will re-download it."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        validated = FileIdParam(file_id=file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file = db.get_file_by_id(validated.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    success = db.mark_corrupted(validated.file_id)
    return {
        "success": success,
        "file_id": validated.file_id,
        "message": "Als korrupt markiert – wird beim nächsten Sync neu heruntergeladen" if success else "Markierung fehlgeschlagen"
    }


@app.post("/api/files/{file_id}/mark-upload-pending")
async def mark_file_upload_pending(file_id: str):
    """Mark a file for re-upload to Nextcloud on next downloader run."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        validated = FileIdParam(file_id=file_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file = db.get_file_by_id(validated.file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    success = db.mark_upload_pending(validated.file_id)
    return {
        "success": success,
        "file_id": validated.file_id,
        "message": "Für Re-Upload vorgemerkt" if success else "Markierung fehlgeschlagen"
    }


@app.post("/api/files/mass-revalidate")
async def mass_revalidate(
    channel_id: Optional[str] = Query(default=None, max_length=100),
    sender: Optional[str] = Query(default=None, max_length=100)
):
    """Mark all matching files as corrupted for mass re-download/revalidation.

    All marked files will be re-downloaded and revalidated on the next downloader run.
    """
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    # Sanitize inputs
    params = SearchParams(channel_id=channel_id, sender=sender)
    count = db.mark_all_for_revalidation(
        channel_id=params.channel_id,
        sender=params.sender
    )

    filter_desc = ""
    if params.channel_id:
        filter_desc += f" in Kanal {params.channel_id}"
    if params.sender:
        filter_desc += f" von {params.sender}"

    return {
        "success": count > 0,
        "count": count,
        "message": f"{count} Dateien{filter_desc} für Revalidierung markiert"
    }


@app.get("/api/filters")
async def get_filters():
    """Get available filter options (channels, senders)."""
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    return {
        "channels": db.get_unique_channels(),
        "senders": db.get_unique_senders()
    }


# --- Helper Functions ---

def format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable string."""
    if bytes_value is None:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_value) < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def is_safe_path(path: Path, base_dir: Path) -> bool:
    """Check if path is within the allowed base directory."""
    try:
        resolved_path = path.resolve()
        resolved_base = base_dir.resolve()
        return str(resolved_path).startswith(str(resolved_base))
    except Exception:
        return False


# --- Main Entry Point ---

def run_server():
    """Run the web server."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting Hermine Mediatool Web UI on {WEB_HOST}:{WEB_PORT}")
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT)


if __name__ == "__main__":
    run_server()
