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

    async def upload_file(self, local_path: Path, filename: str) -> str:
        """Upload file to Nextcloud"""
        remote_file_path = f"{self.remote_path}/{filename}"
        remote_file_path = remote_file_path.lstrip("/")

        # Sicherstellen, dass das Zielverzeichnis existiert
        remote_dir = "/".join(remote_file_path.split("/")[:-1])
        if remote_dir:
            try:
                if not self.client.exists(remote_dir):
                    self.client.mkdir(remote_dir)
            except Exception as e:
                # Wenn der Ordner schon existiert, ignorieren wir den Fehler
                logger.debug(f"Could not create directory {remote_dir}: {e}")

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
