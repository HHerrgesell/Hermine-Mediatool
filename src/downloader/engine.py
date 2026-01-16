"""Download engine for concurrent file downloads."""
import logging
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import time

from src.config import Config
from src.api.hermine_client import HermineClient
from src.api.nextcloud_client import NextcloudClient
from src.storage.database import ManifestDB
from src.storage.path_builder import PathBuilder

logger = logging.getLogger(__name__)


class DownloadEngine:
    """Main download engine."""

    def __init__(self, config: Config, hermine: HermineClient,
                 db: ManifestDB, nextcloud: Optional[NextcloudClient] = None):
        """Initialize download engine."""
        self.config = config
        self.hermine = hermine
        self.db = db
        self.nextcloud = nextcloud
        self.semaphore = asyncio.Semaphore(config.download.max_concurrent_downloads)
        self.stats = {
            'downloaded': 0,
            'skipped': 0,
            'errors': 0,
            'total_size': 0
        }

    async def process_channel(self, channel_id: str) -> Dict:
        """Process all files from a channel."""
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 Verarbeite Kanal: {channel_id}")
        logger.info(f"{'='*70}")

        channel_stats = {
            'downloaded': 0,
            'skipped': 0,
            'errors': 0,
            'total_size': 0
        }

        tasks = []
        message_count = 0

        # Stream all messages and collect download tasks
        for message in self.hermine.stream_all_messages(channel_id, batch_size=50):
            message_count += 1
            if message_count % 100 == 0:
                logger.info(f"  Nachrichten gelesen: {message_count}...")

            # Get media files from message
            media_files = self.hermine.get_media_files(channel_id, message.id)

            for media_file in media_files:
                # Check if already downloaded
                if self.db.file_exists(media_file.id):
                    logger.debug(f"⊘ Übersprungen (existiert): {media_file.filename}")
                    channel_stats['skipped'] += 1
                    continue

                # Check file size limit
                if self.config.download.max_file_size_mb > 0:
                    max_size = self.config.download.max_file_size_mb * 1024 * 1024
                    if media_file.size > max_size:
                        logger.warning(f"⊘ Übersprungen (zu groß): {media_file.filename}")
                        channel_stats['skipped'] += 1
                        continue

                # Check MIME type filter
                if self.config.download.allowed_mimetypes:
                    if media_file.mimetype not in self.config.download.allowed_mimetypes:
                        logger.debug(f"⊘ Übersprungen (MIME-Type): {media_file.filename}")
                        channel_stats['skipped'] += 1
                        continue

                # Create download task
                task = self._download_with_retry(
                    media_file, channel_id, message.sender_name
                )
                tasks.append(task)

        logger.info(f"  Nachrichten gesamt: {message_count}")
        logger.info(f"  Downloads geplant: {len(tasks)}")

        # Execute download tasks
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    for key in ['downloaded', 'skipped', 'errors', 'total_size']:
                        channel_stats[key] += result.get(key, 0)

        # Update global stats
        for key in channel_stats:
            self.stats[key] += channel_stats[key]

        logger.info(f"\n✅ Kanal fertig: {channel_id}")
        logger.info(f"  Heruntergeladen: {channel_stats['downloaded']}")
        logger.info(f"  Übersprungen: {channel_stats['skipped']}")
        logger.info(f"  Fehler: {channel_stats['errors']}")
        logger.info(f"  Größe: {channel_stats['total_size'] / 1024 / 1024:.2f} MB")

        return channel_stats

    async def _download_with_retry(self, media_file, channel_id: str, sender_name: Optional[str]) -> Dict:
        """Download file with retry logic."""
        for attempt in range(self.config.download.retry_attempts):
            try:
                async with self.semaphore:
                    return await self._download_file(media_file, channel_id, sender_name)
            except Exception as e:
                delay = self.config.download.retry_delay * (self.config.download.retry_backoff ** attempt)
                if attempt < self.config.download.retry_attempts - 1:
                    logger.warning(f"⚠️  Fehler bei {media_file.filename}, Versuch {attempt + 1}/{self.config.download.retry_attempts}. Warte {delay:.1f}s...")
                    self.db.add_error(media_file.id, str(e), 'download', attempt + 1)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Fehler beim Download von {media_file.filename}: {e}")
                    self.db.add_error(media_file.id, str(e), 'download', attempt + 1)
                    return {'downloaded': 0, 'skipped': 0, 'errors': 1, 'total_size': 0}

    async def _download_file(self, media_file, channel_id: str, sender_name: Optional[str]) -> Dict:
        """Download a single file."""
        try:
            # Download file content
            logger.debug(f"📥 Downloading: {media_file.filename}")
            content = self.hermine.download_file(media_file.id, channel_id)

            if not content:
                raise Exception("Empty file content")

            # Calculate checksum
            checksum = None
            if self.config.storage.calculate_checksums:
                checksum = hashlib.sha256(content).hexdigest()
                if self.db.checksum_exists(checksum):
                    logger.info(f"⊘ Duplikat erkannt (Checksum): {media_file.filename}")
                    return {'downloaded': 0, 'skipped': 1, 'errors': 0, 'total_size': 0}

            # Build file path
            file_path = PathBuilder.build_path(
                self.config.storage.base_dir,
                self.config.storage.path_template,
                media_file.filename,
                sender_name=sender_name,
                channel_name=channel_id,
                timestamp=media_file.created_at
            )

            # Write file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(content)

            logger.info(f"✓ Heruntergeladen: {media_file.filename} ({len(content) / 1024 / 1024:.2f} MB)")

            # Add to database
            self.db.add_file(
                file_id=media_file.id,
                filename=media_file.filename,
                file_path=str(file_path),
                size=len(content),
                mimetype=media_file.mimetype,
                channel_id=channel_id,
                channel_name=channel_id,
                sender_id=media_file.sender_id,
                sender_name=sender_name,
                message_id=media_file.id,
                checksum=checksum
            )

            # Upload to Nextcloud if configured
            if self.config.nextcloud.enabled and self.config.nextcloud.auto_upload:
                try:
                    remote_path = await self.nextcloud.upload_file(
                        file_path,
                        f"{channel_id}/{file_path.name}"
                    )
                    logger.debug(f"☁️  Zu Nextcloud hochgeladen: {remote_path}")

                    # Delete local file if configured
                    if self.config.nextcloud.delete_local_after_upload:
                        file_path.unlink()
                        logger.debug(f"🗑️  Lokale Datei gelöscht: {media_file.filename}")

                except Exception as e:
                    logger.error(f"Nextcloud Upload fehlgeschlagen: {e}")

            return {
                'downloaded': 1,
                'skipped': 0,
                'errors': 0,
                'total_size': len(content)
            }

        except Exception as e:
            logger.error(f"Fehler beim Download von {media_file.filename}: {e}")
            self.db.add_error(media_file.id, str(e), 'download')
            raise

    def print_statistics(self):
        """Print download statistics."""
        logger.info(f"\n{'='*70}")
        logger.info("📊 FINAL STATISTICS")
        logger.info(f"{'='*70}")
        logger.info(f"  Dateien heruntergeladen: {self.stats['downloaded']}")
        logger.info(f"  Übersprungen: {self.stats['skipped']}")
        logger.info(f"  Fehler: {self.stats['errors']}")
        logger.info(f"  Gesamt-Größe: {self.stats['total_size'] / 1024 / 1024:.2f} MB")
