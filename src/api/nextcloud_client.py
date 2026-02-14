"""Nextcloud WebDAV Client"""
import asyncio
import logging
import time
from pathlib import Path
import httpx
from webdav4.client import Client as WebDAVClient

logger = logging.getLogger(__name__)


class NextcloudClient:
    """Nextcloud WebDAV Integration Client"""

    def __init__(self, url: str, username: str, password: str, remote_path: str,
                 connect_timeout: int = 30, upload_timeout: int = 120):
        """Initialize Nextcloud client.

        Does NOT raise on connection failure - stores state and allows reconnect later.
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.remote_path = remote_path.strip('/')
        self.connect_timeout = connect_timeout
        self.upload_timeout = upload_timeout
        self._connected = False

        # Build WebDAV URL
        self.webdav_url = f"{self.url}/remote.php/dav/files/{username}/"

        try:
            self.client = WebDAVClient(
                base_url=self.webdav_url,
                auth=(username, password),
                timeout=httpx.Timeout(
                    connect=connect_timeout,
                    read=upload_timeout,
                    write=upload_timeout,
                    pool=connect_timeout,
                ),
            )
            self._verify_connection()
        except Exception as e:
            logger.warning(f"Nextcloud Verbindung fehlgeschlagen (wird später erneut versucht): {e}")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if Nextcloud connection is established."""
        return self._connected

    def _verify_connection(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        """Verify WebDAV connection with retry logic."""
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                if not self.client.exists(self.remote_path):
                    self.client.mkdir(self.remote_path)
                self._connected = True
                logger.info(f"Nextcloud WebDAV verbunden: {self.webdav_url}{self.remote_path}")
                return
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"WebDAV connection attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    time.sleep(wait)

        self._connected = False
        logger.error(f"WebDAV-Verbindung fehlgeschlagen nach {max_retries} Versuchen: {last_error}")

    def reconnect(self) -> bool:
        """Re-attempt Nextcloud connection.

        Returns:
            True if connection succeeded, False otherwise
        """
        logger.info("Versuche Nextcloud-Reconnect...")
        try:
            self.client = WebDAVClient(
                base_url=self.webdav_url,
                auth=(self.username, self.password),
                timeout=httpx.Timeout(
                    connect=self.connect_timeout,
                    read=self.upload_timeout,
                    write=self.upload_timeout,
                    pool=self.connect_timeout,
                ),
            )
            self._verify_connection()
            return self._connected
        except Exception as e:
            logger.warning(f"Nextcloud Reconnect fehlgeschlagen: {e}")
            self._connected = False
            return False

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
                    logger.debug(f"Remote-Verzeichnis erstellt: {current_path}")
            except Exception as e:
                # Directory might already exist or be created by another concurrent upload
                logger.debug(f"Verzeichnis {current_path}: {e}")

    async def upload_file(self, local_path: Path, remote_path: str,
                          max_retries: int = 3, retry_delay: float = 3.0) -> str:
        """Upload file to Nextcloud with retry logic and templated path support.

        Args:
            local_path: Local file path
            remote_path: Remote path (can include directories, e.g., '2026/01/sender_file.jpg')
            max_retries: Number of retry attempts
            retry_delay: Base delay between retries (doubles each retry)

        Returns:
            Remote file path on success

        Raises:
            RuntimeError: If all upload attempts fail
        """
        if not self._connected:
            raise RuntimeError("Nextcloud nicht verbunden - Upload nicht möglich")

        remote_file_path = f"{self.remote_path}/{remote_path}"
        remote_file_path = remote_file_path.lstrip("/")

        # Ensure all parent directories exist (create recursively)
        remote_dir = "/".join(remote_file_path.split("/")[:-1])
        if remote_dir:
            self._ensure_remote_dirs(remote_dir)

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                def _upload_file_sync():
                    with open(local_path, "rb") as f:
                        self.client.upload_fileobj(f, remote_file_path, overwrite=True)

                await asyncio.to_thread(_upload_file_sync)
                logger.debug(f"Zu Nextcloud hochgeladen: {remote_file_path}")
                return remote_file_path

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Nextcloud upload attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Nextcloud upload fehlgeschlagen nach {max_retries} Versuchen: {e}")

        raise RuntimeError(
            f"Upload von {local_path.name} nach Nextcloud fehlgeschlagen "
            f"nach {max_retries} Versuchen: {last_error}"
        )

    async def upload_file_with_verification(self, local_path: Path, remote_path: str,
                                              max_retries: int = 3, retry_delay: float = 3.0) -> str:
        """Upload file and verify it exists on Nextcloud with correct size.

        If the uploaded file size doesn't match the local file, deletes the
        remote file and retries.

        Args:
            local_path: Local file path
            remote_path: Remote path (can include directories)
            max_retries: Number of retry attempts
            retry_delay: Base delay between retries

        Returns:
            Remote file path on success

        Raises:
            RuntimeError: If upload or verification fails after all retries
        """
        local_size = local_path.stat().st_size
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                uploaded_path = await self.upload_file(local_path, remote_path)

                # Verify the file exists and has correct size
                remote_info = await asyncio.to_thread(self._get_file_info, uploaded_path)
                if remote_info is None:
                    raise RuntimeError(f"Upload-Verifikation fehlgeschlagen: {uploaded_path} nicht gefunden")

                remote_size = remote_info.get('content_length', 0)
                if remote_size > 0 and remote_size != local_size:
                    logger.warning(
                        f"Upload-Verifikation: Groessenmismatch fuer {uploaded_path} "
                        f"(lokal: {local_size}, remote: {remote_size}). Loesche und wiederhole..."
                    )
                    await self.delete_file(uploaded_path)
                    raise RuntimeError(f"Size mismatch: local={local_size}, remote={remote_size}")

                logger.debug(f"Upload verifiziert: {uploaded_path} ({local_size} bytes)")
                return uploaded_path

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = retry_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Upload-Verifikation Versuch {attempt}/{max_retries} fehlgeschlagen: {e}. "
                        f"Wiederhole in {wait:.1f}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Upload-Verifikation endgueltig fehlgeschlagen: {e}")

        raise RuntimeError(
            f"Upload mit Verifikation fehlgeschlagen nach {max_retries} Versuchen: {last_error}"
        )

    def _get_file_info(self, remote_path: str) -> dict:
        """Get file info from Nextcloud (synchronous).

        Returns:
            Dict with file info including 'content_length', or None if not found.
        """
        try:
            info = self.client.info(remote_path)
            return info
        except Exception:
            return None

    async def delete_file(self, remote_path: str) -> bool:
        """Delete a file from Nextcloud.

        Args:
            remote_path: Remote file path to delete

        Returns:
            True if deleted, False if not found or error
        """
        if not self._connected:
            return False
        try:
            def _delete_sync():
                if self.client.exists(remote_path):
                    self.client.remove(remote_path)
                    return True
                return False

            result = await asyncio.to_thread(_delete_sync)
            if result:
                logger.info(f"Nextcloud-Datei geloescht: {remote_path}")
            return result
        except Exception as e:
            logger.warning(f"Nextcloud-Datei loeschen fehlgeschlagen ({remote_path}): {e}")
            return False

    async def file_exists(self, remote_path: str) -> bool:
        """Check if file exists in Nextcloud"""
        if not self._connected:
            return False
        try:
            return self.client.exists(remote_path)
        except Exception:
            return False
