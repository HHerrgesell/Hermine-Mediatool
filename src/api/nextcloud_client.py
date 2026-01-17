"""Nextcloud WebDAV Client"""
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
            # mkdir ist idempotent, löst aber einen Fehler aus, wenn der Ordner existiert –
            # daher exist_ok=True verwenden.
            self.client.mkdir(self.remote_path, exist_ok=True)
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
                self.client.mkdir(remote_dir, exist_ok=True)
            except Exception:
                # Wenn der Ordner schon existiert, ignorieren wir den Fehler
                pass

        # Upload durchführen
        with open(local_path, "rb") as f:
            self.client.upload_fileobj(remote_file_path, f)

        logger.debug(f"✓ Zu Nextcloud hochgeladen: {remote_file_path}")
        return remote_file_path

    async def file_exists(self, remote_path: str) -> bool:
        """Check if file exists in Nextcloud"""
        try:
            return self.client.exists(remote_path)
        except Exception:
            return False
