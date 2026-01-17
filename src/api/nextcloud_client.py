"""Nextcloud WebDAV Client"""
import logging
from pathlib import Path
from typing import Optional
from webdav4.client import Client as WebDAVClient
from webdav4.exceptions import WebDAVException

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
                auth=(username, password)
            )
            self._verify_connection()
        except Exception as e:
            logger.error(f"✗ Nextcloud Verbindung fehlgeschlagen: {e}")
            raise

    def _verify_connection(self) -> None:
        """Verify WebDAV connection"""
        try:
            self.client.mkdir(self.remote_path)
            logger.info(f"✓ Nextcloud WebDAV verbunden: {self.webdav_url}")
        except WebDAVException as e:
            if '405' not in str(e):  # 405 means path already exists
                logger.error(f"✗ WebDAV-Verbindung fehlgeschlagen: {e}")
                raise
            logger.info(f"✓ Nextcloud WebDAV verbunden")

    async def upload_file(self, local_path: Path, filename: str) -> str:
        """Upload file to Nextcloud"""
        try:
            remote_file_path = f"{self.remote_path}/{filename}"
            
            # Ensure directory exists
            remote_dir = '/'.join(remote_file_path.split('/')[:-1])
            try:
                self.client.mkdir(remote_dir)
            except WebDAVException:
                pass  # Directory might already exist
            
            # Upload file
            with open(local_path, 'rb') as f:
                self.client.upload_sync(remote_file_path, f)
            
            logger.debug(f"✓ Zu Nextcloud hochgeladen: {remote_file_path}")
            return remote_file_path
            
        except WebDAVException as e:
            logger.error(f"✗ Nextcloud Upload fehlgeschlagen: {e}")
            raise

    async def file_exists(self, remote_path: str) -> bool:
        """Check if file exists in Nextcloud"""
        try:
            return self.client.exists(remote_path)
        except WebDAVException:
            return False
