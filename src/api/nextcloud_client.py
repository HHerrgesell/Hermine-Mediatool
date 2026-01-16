"""Nextcloud WebDAV client for file uploads."""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NextcloudClient:
    """WebDAV Client für Nextcloud"""

    def __init__(self, base_url: str, username: str, password: str,
                 remote_path: str = "/Hermine-Media/"):
        """Initialisiere Nextcloud Client"""
        try:
            from webdav4.client import Client as WebDAVClient
        except ImportError:
            raise ImportError("webdav4 nicht installiert: pip install webdav4")

        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.remote_path = remote_path.strip('/').lstrip('/')

        # WebDAV URL
        self.webdav_url = f"{self.base_url}/remote.php/dav/files/{username}/"

        self.client = WebDAVClient(
            base_url=self.webdav_url,
            auth=(username, password)
        )

        self._verify_connection()

    def _verify_connection(self):
        """Verifiziere Verbindung"""
        try:
            self.client.ls('/')
            logger.info("✓ Nextcloud WebDAV verbunden")
        except Exception as e:
            raise Exception(f"Nextcloud Verbindung fehlgeschlagen: {e}")

    async def upload_file(self, local_path: Path, filename: str) -> str:
        """Lade Datei zu Nextcloud hoch"""
        try:
            # Ziel-Pfad
            remote_file = f"{self.remote_path}/{filename}"

            # Upload
            with open(local_path, 'rb') as f:
                self.client.upload(remote_file, f)

            logger.debug(f"✓ Zu Nextcloud hochgeladen: {remote_file}")
            return remote_file

        except Exception as e:
            logger.error(f"Nextcloud Upload fehlgeschlagen: {e}")
            raise
