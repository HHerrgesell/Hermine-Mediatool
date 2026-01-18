"""Nextcloud WebDAV Client"""
import asyncio
import logging
from pathlib import Path
from webdav4.client import Client as WebDAVClient

logger = logging.getLogger(__name__)


class NextcloudClient:
    """Nextcloud WebDAV Integration Client"""

    def __init__(self, url: str, username: str, password: str, remote_path: str):
        """Initialize Nextcloud client"""
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.remote_path = remote_path.strip('/')

        # Build WebDAV URL
        self.webdav_url = f"{self.url}/remote.php/dav/files/{username}/"

        try:
            self.client = WebDAVClient(
                base_url=self.webdav_url,
                auth=(username, password),
            )
            self._verify_connection()
        except Exception as e:
            logger.error(f"✗ Nextcloud Verbindung fehlgeschlagen: {e}")
            raise

    def _verify_connection(self) -> None:
        """Verify WebDAV connection"""
        try:
            # Try to create the remote path, ignore if it already exists
            if not self.client.exists(self.remote_path):
                self.client.mkdir(self.remote_path)
            logger.info(f"✓ Nextcloud WebDAV verbunden: {self.webdav_url}{self.remote_path}")
        except Exception as e:
            logger.error(f"✗ WebDAV-Verbindung fehlgeschlagen: {e}")
            raise

    def _ensure_remote_dirs(self, remote_dir: str) -> None:
        """Recursively create remote directories if they don't exist.

        Args:
            remote_dir: Remote directory path (e.g., 'Hermine-Media/2026/01')
        """
        parts = remote_dir.split("/")
        current_path = ""

        for part in parts:
            if not part:
                continue
            current_path = f"{current_path}/{part}" if current_path else part
            try:
                if not self.client.exists(current_path):
                    self.client.mkdir(current_path)
                    logger.debug(f"✓ Remote-Verzeichnis erstellt: {current_path}")
            except Exception as e:
                # Directory might already exist or be created by another concurrent upload
                logger.debug(f"Verzeichnis {current_path}: {e}")

    async def upload_file(self, local_path: Path, remote_path: str) -> str:
        """Upload file to Nextcloud with templated path support.

        Args:
            local_path: Path to local file to upload
            remote_path: Remote path (can include directories, e.g., '2026/01/sender_file.jpg')

        Returns:
            Full remote path where file was uploaded
        """
        remote_file_path = f"{self.remote_path}/{remote_path}"
        remote_file_path = remote_file_path.lstrip("/")

        # Ensure all parent directories exist (create recursively)
        remote_dir = "/".join(remote_file_path.split("/")[:-1])
        if remote_dir:
            self._ensure_remote_dirs(remote_dir)

        # Upload durchführen (run blocking I/O in thread pool to avoid blocking event loop)
        def _upload_file_sync():
            with open(local_path, "rb") as f:
                self.client.upload_fileobj(f, remote_file_path)  # Correct parameter order

        await asyncio.to_thread(_upload_file_sync)

        logger.debug(f"✓ Zu Nextcloud hochgeladen: {remote_file_path}")
        return remote_file_path

    async def file_exists(self, remote_path: str) -> bool:
        """Check if file exists in Nextcloud"""
        try:
            return self.client.exists(remote_path)
        except Exception:
            return False
