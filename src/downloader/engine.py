"""Download Engine - Core download orchestration"""
import asyncio
import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.config import Config
from src.api.hermine_client import HermineClient, MediaFile
from src.api.nextcloud_client import NextcloudClient
from src.storage.database import ManifestDB
from src.storage.path_builder import PathBuilder
from src.downloader.exif_processor import EXIFProcessor

logger = logging.getLogger(__name__)

# Minimum file size to accept (thumbnails are ~4-5KB)
MIN_FILE_SIZE_BYTES = 10 * 1024  # 10KB


class DownloadEngine:
    """Async Download Engine with deduplication and error handling"""

    def __init__(self, config: Config, hermine: HermineClient,
                 database: ManifestDB, nextcloud: Optional[NextcloudClient] = None):
        """Initialize download engine"""
        self.config = config
        self.hermine = hermine
        self.db = database
        self.nextcloud = nextcloud
        self.semaphore = asyncio.Semaphore(config.download.max_concurrent_downloads)
        self.stats = {
            'downloaded': 0, 'skipped': 0, 'errors': 0, 'total_size': 0,
            'uploads_retried': 0, 'corrupted_redownloaded': 0,
        }
        self.exif_processor = EXIFProcessor(config)

    async def retry_pending_uploads(self) -> int:
        """Retry uploading files that previously failed or are pending.

        For files where the local file is missing, deletes the DB record
        so they get re-downloaded and re-uploaded in the normal channel
        processing flow.

        Returns:
            Number of successfully uploaded files
        """
        if not self.nextcloud or not self.nextcloud.is_connected:
            return 0

        pending_files = self.db.get_files_needing_upload()
        if not pending_files:
            return 0

        logger.info(f"Wiederhole {len(pending_files)} ausstehende Uploads...")
        success_count = 0
        cleared_for_redownload = 0

        for file_info in pending_files:
            local_path_str = file_info.get('local_path')

            # If no local file path or file doesn't exist, clear record for re-download
            if not local_path_str:
                # Delete any corrupt/partial file on Nextcloud if it exists
                if file_info.get('nextcloud_path'):
                    await self.nextcloud.delete_file(file_info['nextcloud_path'])
                self.db.delete_file_record(file_info['file_id'])
                cleared_for_redownload += 1
                logger.info(f"Fuer Re-Download freigegeben (kein lokaler Pfad): {file_info['filename']}")
                continue

            local_path = Path(local_path_str)
            if not local_path.exists():
                # Delete any corrupt/partial file on Nextcloud if it exists
                if file_info.get('nextcloud_path'):
                    await self.nextcloud.delete_file(file_info['nextcloud_path'])
                self.db.delete_file_record(file_info['file_id'])
                cleared_for_redownload += 1
                logger.info(f"Fuer Re-Download freigegeben (Datei fehlt): {file_info['filename']}")
                continue

            try:
                nc_remote_path = self._build_retry_remote_path(file_info)
                nc_path = await self.nextcloud.upload_file_with_verification(
                    local_path, nc_remote_path
                )
                self.db.update_file(
                    file_info['file_id'],
                    status='completed',
                    nextcloud_path=nc_path
                )

                if self.config.nextcloud.delete_local_after_upload:
                    local_path.unlink(missing_ok=True)
                    logger.debug(f"Lokale Datei geloescht nach Upload: {file_info['filename']}")

                success_count += 1
                logger.info(f"Upload nachgeholt: {file_info['filename']}")

            except Exception as e:
                logger.warning(f"Upload-Wiederholung fehlgeschlagen fuer {file_info['filename']}: {e}")
                self.db.mark_upload_failed(file_info['file_id'])

        self.stats['uploads_retried'] = success_count
        if cleared_for_redownload > 0:
            logger.info(f"{cleared_for_redownload} Dateien fuer Re-Download freigegeben")
        logger.info(f"Upload-Wiederholung: {success_count}/{len(pending_files)} erfolgreich")
        return success_count

    async def redownload_corrupted_files(self) -> int:
        """Re-download files that were marked as corrupted.

        Deletes corrupt files from Nextcloud and local storage, then clears
        the DB record so files get re-downloaded in the normal flow.

        Returns:
            Number of corrupted records cleared for re-download
        """
        corrupted = self.db.get_corrupted_files()
        if not corrupted:
            return 0

        logger.info(f"Bereinige {len(corrupted)} korrupte Dateien fuer Re-Download...")
        cleared = 0

        for file_info in corrupted:
            # Delete corrupt file from Nextcloud if it exists there
            if file_info.get('nextcloud_path') and self.nextcloud and self.nextcloud.is_connected:
                await self.nextcloud.delete_file(file_info['nextcloud_path'])

            # Delete local corrupted file if it exists
            if file_info.get('local_path'):
                local_path = Path(file_info['local_path'])
                if local_path.exists():
                    local_path.unlink(missing_ok=True)
                    logger.debug(f"Korrupte lokale Datei geloescht: {local_path}")

            # Delete the DB record so file_exists() returns False and it gets re-downloaded
            self.db.delete_file_record(file_info['file_id'])
            cleared += 1

        self.stats['corrupted_redownloaded'] = cleared
        logger.info(f"{cleared} korrupte Dateien zum Re-Download freigegeben")
        return cleared

    async def process_channel(self, channel_id: str) -> Dict[str, Any]:
        """Process all media files in a channel"""
        stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'total_size': 0}

        try:
            logger.info(f"\nVerarbeite Kanal: {channel_id}")
            media_files = await self.hermine.get_media_files(channel_id)

            if not media_files:
                logger.info(f"Keine Mediadateien in Kanal {channel_id}")
                return stats

            # Filter already downloaded files (only completed ones are skipped)
            new_files = []
            for mf in media_files:
                if self.db.file_exists(mf.file_id):
                    stats['skipped'] += 1
                else:
                    new_files.append(mf)

            logger.info(f"  -> {len(new_files)} neue Dateien, {stats['skipped']} uebersprungen")

            if not new_files:
                return stats

            # Start parallel downloads
            tasks = [self._download_file_safe(mf) for mf in new_files]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, dict):
                    stats['downloaded'] += result['downloaded']
                    stats['errors'] += result['errors']
                    stats['total_size'] += result['total_size']

            self.stats['downloaded'] += stats['downloaded']
            self.stats['skipped'] += stats['skipped']
            self.stats['errors'] += stats['errors']
            self.stats['total_size'] += stats['total_size']
            return stats

        except Exception as e:
            logger.error(f"Fehler bei Kanal {channel_id}: {e}")
            stats['errors'] += 1
            return stats

    async def _download_file_safe(self, media_file: MediaFile) -> Dict[str, Any]:
        """Download file with error handling"""
        result = {'downloaded': 0, 'errors': 0, 'total_size': 0}

        async with self.semaphore:
            retry_count = 0
            while retry_count < self.config.download.retry_attempts:
                try:
                    # Download file (with decryption if encrypted)
                    logger.debug(f"Downloade: {media_file.filename}")
                    file_data = await self.hermine.download_file(
                        media_file,
                        timeout=self.config.download.download_timeout
                    )

                    # Validate file data before saving
                    self._validate_file_data(file_data, media_file)

                    # Save locally using PathBuilder
                    local_path = self._get_local_path(media_file)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(file_data)

                    # Process EXIF data - check/set Author from sender name
                    if self.config.storage.extract_metadata:
                        self.exif_processor.process_file(
                            local_path,
                            preserve_timestamp=True,
                            sender_name=media_file.sender_name
                        )

                    # Calculate hash
                    file_hash = hashlib.sha256(file_data).hexdigest() if self.config.storage.calculate_checksums else None
                    file_size = len(file_data)

                    # Upload to Nextcloud (optional) - use templated path
                    nc_path = None
                    upload_status = 'completed'

                    if self.nextcloud and self.config.nextcloud.auto_upload:
                        if self.nextcloud.is_connected:
                            try:
                                nc_remote_path = self._get_templated_path(media_file)
                                nc_path = await self.nextcloud.upload_file_with_verification(
                                    local_path,
                                    nc_remote_path
                                )

                                if self.config.nextcloud.delete_local_after_upload:
                                    local_path.unlink()
                                    logger.debug(f"Lokale Datei geloescht: {media_file.filename}")
                            except Exception as e:
                                logger.warning(f"Nextcloud Upload fehlgeschlagen: {e}")
                                upload_status = 'upload_failed'
                        else:
                            # Nextcloud not connected - save locally and mark for later upload
                            upload_status = 'upload_pending'
                            logger.debug(f"Nextcloud nicht verbunden, Upload vorgemerkt: {media_file.filename}")

                    # Store local_path BEFORE checking exists (deletion happens above)
                    stored_local_path = str(local_path) if local_path.exists() else None

                    # Update database (use upsert to handle re-processing)
                    self.db.upsert_file(
                        file_id=media_file.file_id,
                        channel_id=media_file.channel_id,
                        message_id=media_file.message_id,
                        filename=media_file.filename,
                        file_hash=file_hash,
                        file_size=file_size,
                        mime_type=media_file.mime_type,
                        sender=media_file.sender_name,
                        local_path=stored_local_path,
                        nextcloud_path=nc_path,
                        status=upload_status,
                    )

                    logger.info(f"{media_file.filename} ({file_size / 1024 / 1024:.2f} MB) [{upload_status}]")
                    result['downloaded'] = 1
                    result['total_size'] = file_size
                    return result

                except Exception as e:
                    retry_count += 1
                    if retry_count < self.config.download.retry_attempts:
                        wait_time = self.config.download.retry_delay * (self.config.download.retry_backoff ** (retry_count - 1))
                        logger.warning(f"Fehler (Versuch {retry_count}/{self.config.download.retry_attempts}): {e}. Warte {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"{media_file.filename}: {e}")
                        self.db.record_error(media_file.file_id, str(e))
                        result['errors'] = 1
                        return result

        result['errors'] = 1
        return result

    @staticmethod
    def _validate_file_data(file_data: bytes, media_file: MediaFile) -> None:
        """Validate downloaded file data to catch corrupted/thumbnail-only downloads.

        Args:
            file_data: The downloaded file bytes
            media_file: The MediaFile metadata

        Raises:
            ValueError: If validation fails
        """
        file_size = len(file_data)

        # Check minimum file size (thumbnails are ~4-5KB)
        if file_size < MIN_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too small ({file_size} bytes, minimum {MIN_FILE_SIZE_BYTES}). "
                f"Likely a thumbnail, not the full file."
            )

        # For image files: verify PIL can open them
        if media_file.mime_type.startswith('image/'):
            try:
                from PIL import Image
                img = Image.open(BytesIO(file_data))
                img.verify()
            except Exception as e:
                raise ValueError(
                    f"Image validation failed for {media_file.filename}: {e}"
                )

    def _get_local_path(self, media_file: MediaFile) -> Path:
        """Determine local file path based on configuration"""
        timestamp = self._parse_timestamp(media_file.timestamp)

        return PathBuilder.build_path(
            base_dir=self.config.storage.base_dir,
            template=self.config.storage.path_template,
            filename=media_file.filename,
            sender_name=media_file.sender_name,
            channel_name=media_file.channel_id,
            timestamp=timestamp
        )

    def _get_templated_path(self, media_file: MediaFile) -> str:
        """Get templated relative path for uploads (e.g., Nextcloud).

        Returns the path using the configured template without the base directory.
        """
        timestamp = self._parse_timestamp(media_file.timestamp)

        # Sanitize components
        sender_safe = PathBuilder._sanitize_name(media_file.sender_name or 'Unknown')
        channel_safe = PathBuilder._sanitize_name(media_file.channel_id or 'Unknown')
        filename_safe = PathBuilder._sanitize_filename(media_file.filename)

        # Replace template placeholders
        path_str = self.config.storage.path_template
        replacements = {
            'year': str(timestamp.year),
            'month': str(timestamp.month),
            'month:02d': f"{timestamp.month:02d}",
            'day': str(timestamp.day),
            'day:02d': f"{timestamp.day:02d}",
            'sender': sender_safe,
            'filename': filename_safe,
            'channel_name': channel_safe
        }

        for placeholder, value in replacements.items():
            path_str = path_str.replace('{' + placeholder + '}', value)

        return path_str

    def _build_retry_remote_path(self, file_info: dict) -> str:
        """Build a templated remote path for retry uploads from DB record data.

        Reconstructs the same path structure as _get_templated_path would produce
        for a fresh download, using the stored sender, filename, and timestamp.
        """
        sender = file_info.get('sender') or 'Unknown'
        filename = file_info.get('filename', 'unknown')
        timestamp_str = file_info.get('download_timestamp')

        # Parse the DB timestamp (ISO format: 2026-02-12 22:02:18)
        timestamp = datetime.now()
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                pass

        sender_safe = PathBuilder._sanitize_name(sender)
        filename_safe = PathBuilder._sanitize_filename(filename)
        channel_safe = PathBuilder._sanitize_name(file_info.get('channel_id') or 'Unknown')

        path_str = self.config.storage.path_template
        replacements = {
            'year': str(timestamp.year),
            'month': str(timestamp.month),
            'month:02d': f"{timestamp.month:02d}",
            'day': str(timestamp.day),
            'day:02d': f"{timestamp.day:02d}",
            'sender': sender_safe,
            'filename': filename_safe,
            'channel_name': channel_safe
        }

        for placeholder, value in replacements.items():
            path_str = path_str.replace('{' + placeholder + '}', value)

        return path_str

    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> datetime:
        """Parse a timestamp string into a datetime object."""
        try:
            if timestamp_str and timestamp_str.isdigit():
                return datetime.fromtimestamp(int(timestamp_str))
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
        except (ValueError, OSError):
            pass
        return datetime.now()

    def print_statistics(self) -> None:
        """Print download statistics"""
        logger.info(f"\nStatistiken:")
        logger.info(f"  Heruntergeladen: {self.stats['downloaded']}")
        logger.info(f"  Uebersprungen: {self.stats['skipped']}")
        logger.info(f"  Fehler: {self.stats['errors']}")
        logger.info(f"  Groesse: {self.stats['total_size'] / 1024 / 1024:.2f} MB")
        if self.stats.get('uploads_retried'):
            logger.info(f"  Uploads nachgeholt: {self.stats['uploads_retried']}")
        if self.stats.get('corrupted_redownloaded'):
            logger.info(f"  Korrupte re-downloaded: {self.stats['corrupted_redownloaded']}")

        # Show DB-level stats for pending/corrupted
        db_stats = self.db.get_stats()
        if db_stats.get('pending_uploads', 0) > 0:
            logger.warning(f"  Ausstehende Uploads: {db_stats['pending_uploads']}")
        if db_stats.get('corrupted_files', 0) > 0:
            logger.warning(f"  Korrupte Dateien: {db_stats['corrupted_files']}")
