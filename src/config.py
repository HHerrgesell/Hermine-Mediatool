"""Configuration management with validation and error handling."""
import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)


@dataclass
class HermineConfig:
    """Hermine API Konfiguration"""
    base_url: str
    username: str
    password: str
    timeout: int = 30
    verify_ssl: bool = True


@dataclass
class StorageConfig:
    """Speicherungs-Konfiguration"""
    base_dir: Path
    organize_by_channel: bool = True
    organize_by_date: bool = True
    organize_by_sender: bool = True
    path_template: str = "{year}/{month:02d}/{sender}_{filename}"
    create_manifest: bool = True
    max_file_size_mb: int = 5000


@dataclass
class DownloadConfig:
    """Download-Parameter"""
    max_concurrent: int = 5
    chunk_size: int = 8388608  # 8 MB
    retry_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    timeout: int = 60
    allowed_mimetypes: List[str] = field(default_factory=list)
    blocked_mimetypes: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.allowed_mimetypes:
            self.allowed_mimetypes = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'image/bmp', 'image/svg+xml', 'image/tiff',
                'video/mp4', 'video/webm', 'video/quicktime',
                'video/x-msvideo', 'video/x-matroska',
                'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/aac'
            ]


@dataclass
class NextcloudConfig:
    """Nextcloud Integration"""
    enabled: bool = False
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    remote_path: str = "/Hermine-Media/"
    auto_upload: bool = False
    delete_local_after_upload: bool = False


@dataclass
class LoggingConfig:
    """Logging-Konfiguration"""
    level: str = "INFO"
    log_file: Optional[Path] = None
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_output: bool = True


class Config:
    """Zentrale Konfigurationsklasse mit Validierung"""

    def __init__(self, env_file: Optional[Path] = None):
        """Lade Konfiguration aus .env und Umgebungsvariablen"""
        if env_file is None:
            env_file = Path(__file__).parent.parent / ".env"
        
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Konfiguration geladen aus: {env_file}")
        else:
            logger.warning(f".env nicht gefunden unter {env_file}, nutze nur Umgebungsvariablen")

        # Hermine
        self.hermine = HermineConfig(
            base_url=self._get_required("HERMINE_BASE_URL"),
            username=self._get_required("HERMINE_USERNAME"),
            password=self._get_required("HERMINE_PASSWORD"),
            timeout=self._get_int("HERMINE_TIMEOUT", 30),
            verify_ssl=self._get_bool("HERMINE_VERIFY_SSL", True)
        )

        # Storage
        self.storage = StorageConfig(
            base_dir=Path(self._get("DOWNLOAD_DIR", "./downloads")),
            organize_by_channel=self._get_bool("ORGANIZE_BY_CHANNEL", True),
            organize_by_date=self._get_bool("ORGANIZE_BY_DATE", True),
            organize_by_sender=self._get_bool("ORGANIZE_BY_SENDER", True),
            path_template=self._get("PATH_TEMPLATE", "{year}/{month:02d}/{sender}_{filename}"),
            create_manifest=self._get_bool("CREATE_MANIFEST", True),
            max_file_size_mb=self._get_int("MAX_FILE_SIZE_MB", 5000)
        )

        # Download
        self.download = DownloadConfig(
            max_concurrent=self._get_int("MAX_CONCURRENT_DOWNLOADS", 5),
            chunk_size=self._get_int("CHUNK_SIZE", 8388608),
            retry_attempts=self._get_int("RETRY_ATTEMPTS", 3),
            retry_delay=self._get_float("RETRY_DELAY", 1.0),
            retry_backoff=self._get_float("RETRY_BACKOFF", 2.0),
            timeout=self._get_int("DOWNLOAD_TIMEOUT", 60)
        )

        # Nextcloud
        self.nextcloud = NextcloudConfig(
            enabled=self._get_bool("NEXTCLOUD_ENABLED", False),
            url=self._get("NEXTCLOUD_URL"),
            username=self._get("NEXTCLOUD_USERNAME"),
            password=self._get("NEXTCLOUD_PASSWORD"),
            remote_path=self._get("NEXTCLOUD_REMOTE_PATH", "/Hermine-Media/"),
            auto_upload=self._get_bool("NEXTCLOUD_AUTO_UPLOAD", False),
            delete_local_after_upload=self._get_bool("DELETE_LOCAL_AFTER_UPLOAD", False)
        )

        # Logging
        self.logging = LoggingConfig(
            level=self._get("LOG_LEVEL", "INFO"),
            log_file=Path(self._get("LOG_FILE", "hermine_downloader.log")) if self._get("LOG_FILE") else None,
            console_output=self._get_bool("LOG_CONSOLE", True)
        )

        # Target Kanäle
        channels_str = self._get("TARGET_CHANNELS", "")
        self.target_channels = [ch.strip() for ch in channels_str.split(",") if ch.strip()]

        # Features
        self.features = {
            "calculate_checksums": self._get_bool("CALCULATE_CHECKSUMS", True),
            "extract_metadata": self._get_bool("EXTRACT_METADATA", True),
            "generate_thumbnails": self._get_bool("GENERATE_THUMBNAILS", False)
        }

        self._validate()

    def _get(self, key: str, default: str = None) -> str:
        """Sichere Umgebungsvariable abrufen"""
        return os.getenv(key, default)

    def _get_required(self, key: str) -> str:
        """Erforderliche Umgebungsvariable abrufen"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Erforderliche Umgebungsvariable nicht gesetzt: {key}")
        return value

    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Boolean-Umgebungsvariable abrufen"""
        value = os.getenv(key, str(default)).lower()
        return value in ("true", "1", "yes", "on")

    def _get_int(self, key: str, default: int = 0) -> int:
        """Integer-Umgebungsvariable abrufen"""
        try:
            return int(os.getenv(key, default))
        except ValueError:
            logger.warning(f"Ungültige Integer-Variable {key}, nutze default {default}")
            return default

    def _get_float(self, key: str, default: float = 0.0) -> float:
        """Float-Umgebungsvariable abrufen"""
        try:
            return float(os.getenv(key, default))
        except ValueError:
            logger.warning(f"Ungültige Float-Variable {key}, nutze default {default}")
            return default

    def _validate(self):
        """Validiere Konfiguration"""
        if not self.hermine.base_url.startswith(("http://", "https://")):
            raise ValueError(f"Ungültige Hermine Base URL: {self.hermine.base_url}")

        self.storage.base_dir.mkdir(parents=True, exist_ok=True)

        if self.nextcloud.enabled:
            if not all([self.nextcloud.url, self.nextcloud.username, self.nextcloud.password]):
                raise ValueError("Nextcloud enabled aber credentials fehlen")
            if not self.nextcloud.url.startswith(("http://", "https://")):
                raise ValueError(f"Ungültige Nextcloud URL: {self.nextcloud.url}")

        logger.info("✓ Konfiguration validiert")

    def to_dict(self) -> dict:
        """Exportiere Konfiguration als Dictionary"""
        return {
            "hermine_url": self.hermine.base_url,
            "storage_dir": str(self.storage.base_dir),
            "path_template": self.storage.path_template,
            "max_concurrent": self.download.max_concurrent,
            "target_channels": self.target_channels,
            "nextcloud_enabled": self.nextcloud.enabled,
            "log_level": self.logging.level
        }
