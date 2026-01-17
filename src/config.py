"""Configuration management for Hermine downloader."""
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional
from dotenv import load_dotenv


@dataclass
class HermineConfig:
    """Hermine API Configuration"""
    base_url: str
    username: str
    password: str
    encryption_key: str  # Passphrase for RSA private key
    timeout: int = 30
    verify_ssl: bool = True


@dataclass
class NextcloudConfig:
    """Nextcloud WebDAV Configuration"""
    enabled: bool = False
    url: str = ""
    username: str = ""
    password: str = ""
    remote_path: str = "/Hermine-Media/"
    auto_upload: bool = False
    delete_local_after_upload: bool = False


@dataclass
class DownloadConfig:
    """Download Parameter Configuration"""
    max_concurrent_downloads: int = 5
    chunk_size: int = 8388608  # 8MB
    retry_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    download_timeout: int = 60
    allowed_mimetypes: List[str] = field(default_factory=list)
    max_file_size_mb: int = 5000  # 5GB


@dataclass
class StorageConfig:
    """Storage Configuration"""
    base_dir: Path
    path_template: str = "{year}/{month:02d}/{sender}_{filename}"
    organize_by_channel: bool = True
    organize_by_date: bool = True
    organize_by_sender: bool = True
    create_manifest: bool = True
    calculate_checksums: bool = True
    extract_metadata: bool = True
    generate_thumbnails: bool = False


@dataclass
class LogConfig:
    """Logging Configuration"""
    level: str = "INFO"
    file: str = "hermine_downloader.log"
    console: bool = True


class Config:
    """Main Configuration Class"""

    def __init__(self, env_path: Optional[Path] = None):
        """Initialize configuration from .env file or environment variables."""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()

        # Hermine Configuration
        self.hermine = HermineConfig(
            base_url=os.getenv('HERMINE_BASE_URL', 'https://hermine.example.com'),
            username=os.getenv('HERMINE_USERNAME', ''),
            password=os.getenv('HERMINE_PASSWORD', ''),
            encryption_key=os.getenv('HERMINE_ENCRYPTION_KEY', ''),
            timeout=int(os.getenv('HERMINE_TIMEOUT', '30')),
            verify_ssl=os.getenv('HERMINE_VERIFY_SSL', 'true').lower() == 'true'
        )

        # Download Configuration
        target_channels = os.getenv('TARGET_CHANNELS', '')
        self.target_channels = [ch.strip() for ch in target_channels.split(',') if ch.strip()]

        # Storage Configuration
        base_dir = Path(os.getenv('DOWNLOAD_DIR', './downloads'))
        base_dir.mkdir(parents=True, exist_ok=True)

        self.storage = StorageConfig(
            base_dir=base_dir,
            path_template=os.getenv('PATH_TEMPLATE', '{year}/{month:02d}/{sender}_{filename}'),
            organize_by_channel=os.getenv('ORGANIZE_BY_CHANNEL', 'true').lower() == 'true',
            organize_by_date=os.getenv('ORGANIZE_BY_DATE', 'true').lower() == 'true',
            organize_by_sender=os.getenv('ORGANIZE_BY_SENDER', 'true').lower() == 'true',
            create_manifest=os.getenv('CREATE_MANIFEST', 'true').lower() == 'true',
            calculate_checksums=os.getenv('CALCULATE_CHECKSUMS', 'true').lower() == 'true',
            extract_metadata=os.getenv('EXTRACT_METADATA', 'true').lower() == 'true',
            generate_thumbnails=os.getenv('GENERATE_THUMBNAILS', 'false').lower() == 'true'
        )

        # Download Parameters
        self.download = DownloadConfig(
            max_concurrent_downloads=int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '5')),
            chunk_size=int(os.getenv('CHUNK_SIZE', '8388608')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            retry_delay=float(os.getenv('RETRY_DELAY', '1.0')),
            retry_backoff=float(os.getenv('RETRY_BACKOFF', '2.0')),
            download_timeout=int(os.getenv('DOWNLOAD_TIMEOUT', '60')),
            allowed_mimetypes=self._parse_list(os.getenv('ALLOWED_MIMETYPES', '')),
            max_file_size_mb=int(os.getenv('MAX_FILE_SIZE_MB', '5000'))
        )

        # Nextcloud Configuration
        self.nextcloud = NextcloudConfig(
            enabled=os.getenv('NEXTCLOUD_ENABLED', 'false').lower() == 'true',
            url=os.getenv('NEXTCLOUD_URL', ''),
            username=os.getenv('NEXTCLOUD_USERNAME', ''),
            password=os.getenv('NEXTCLOUD_PASSWORD', ''),
            remote_path=os.getenv('NEXTCLOUD_REMOTE_PATH', '/Hermine-Media/'),
            auto_upload=os.getenv('NEXTCLOUD_AUTO_UPLOAD', 'false').lower() == 'true',
            delete_local_after_upload=os.getenv('DELETE_LOCAL_AFTER_UPLOAD', 'false').lower() == 'true'
        )

        # Logging Configuration
        self.logging = LogConfig(
            level=os.getenv('LOG_LEVEL', 'INFO'),
            file=os.getenv('LOG_FILE', 'hermine_downloader.log'),
            console=os.getenv('LOG_CONSOLE', 'true').lower() == 'true'
        )

    @staticmethod
    def _parse_list(value: str) -> List[str]:
        """Parse comma-separated list from environment variable."""
        if not value:
            return []
        return [item.strip() for item in value.split(',') if item.strip()]

    def to_dict(self) -> dict:
        """Convert configuration to dictionary (for logging)."""
        return {
            'hermine': asdict(self.hermine),
            'storage': asdict(self.storage),
            'download': asdict(self.download),
            'nextcloud': asdict(self.nextcloud),
            'logging': asdict(self.logging),
            'target_channels': self.target_channels
        }

    def validate(self) -> bool:
        """Validate configuration."""
        if not self.hermine.base_url:
            raise ValueError("HERMINE_BASE_URL nicht konfiguriert")
        if not self.hermine.username:
            raise ValueError("HERMINE_USERNAME nicht konfiguriert")
        if not self.hermine.password:
            raise ValueError("HERMINE_PASSWORD nicht konfiguriert")
        if not self.hermine.encryption_key:
            raise ValueError("HERMINE_ENCRYPTION_KEY nicht konfiguriert")
        if not self.target_channels:
            raise ValueError("TARGET_CHANNELS nicht konfiguriert")
        return True
