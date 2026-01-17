"""Download Engine - Core download orchestration"""
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from src.config import Config
from src.api.hermine_client import HermineClient, MediaFile
from src.api.nextcloud_client import NextcloudClient
from src.storage.database import ManifestDB

logger = logging.getLogger(__name__)


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
        self.stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'total_size': 0}

    async def process_channel(self, channel_id: str) -> Dict[str, Any]:
        """Process all media files in a channel"""
        stats = {'downloaded': 0, 'skipped': 0, 'errors': 0, 'total_size': 0}
        
        try:
            logger.info(f"\n📁 Verarbeite Kanal: {channel_id}")
            media_files = await self.hermine.get_media_files(channel_id)
            
            if not media_files:
                logger.info(f"ℹ️  Keine Mediadateien in Kanal {channel_id}")
                return stats
            
            # Filter already downloaded files
            new_files = []
            for mf in media_files:
                if self.db.file_exists(mf.file_id):
                    stats['skipped'] += 1
                else:
                    new_files.append(mf)
            
            logger.info(f"  ↳ {len(new_files)} neue Dateien, {stats['skipped']} übersprungen")
            
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
            
            self.stats = stats
            return stats
            
        except Exception as e:
            logger.error(f"✗ Fehler bei Kanal {channel_id}: {e}")
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
                    logger.debug(f"⬇️  Downloade: {media_file.filename}")
                    file_data = await self.hermine.download_file(
                        media_file,
                        timeout=self.config.download.download_timeout
                    )
                    
                    # Save locally
                    local_path = self._get_local_path(media_file)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(file_data)
                    
                    # Calculate hash
                    file_hash = hashlib.sha256(file_data).hexdigest() if self.config.storage.calculate_checksums else None
                    file_size = len(file_data)
                    
                    # Upload to Nextcloud (optional)
                    nc_path = None
                    if self.nextcloud and self.config.nextcloud.auto_upload:
                        try:
                            nc_path = await self.nextcloud.upload_file(
                                local_path,
                                media_file.filename
                            )
                            
                            if self.config.nextcloud.delete_local_after_upload:
                                local_path.unlink()
                                logger.debug(f"🗑️  Lokale Datei gelöscht: {media_file.filename}")
                        except Exception as e:
                            logger.warning(f"⚠️  Nextcloud Upload fehlgeschlagen: {e}")
                    
                    # Update database
                    self.db.insert_file(
                        file_id=media_file.file_id,
                        channel_id=media_file.channel_id,
                        message_id=media_file.message_id,
                        filename=media_file.filename,
                        file_hash=file_hash,
                        file_size=file_size,
                        mime_type=media_file.mime_type,
                        sender=media_file.sender_name,
                        local_path=str(local_path) if not (self.nextcloud and self.config.nextcloud.delete_local_after_upload) else None,
                        nextcloud_path=nc_path
                    )
                    
                    logger.info(f"✓ {media_file.filename} ({file_size / 1024 / 1024:.2f} MB)")
                    result['downloaded'] = 1
                    result['total_size'] = file_size
                    return result
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < self.config.download.retry_attempts:
                        wait_time = self.config.download.retry_delay * (self.config.download.retry_backoff ** (retry_count - 1))
                        logger.warning(f"⚠️  Fehler (Versuch {retry_count}/{self.config.download.retry_attempts}): {e}. Warte {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"✗ {media_file.filename}: {e}")
                        self.db.record_error(media_file.file_id, str(e))
                        result['errors'] = 1
                        return result
        
        result['errors'] = 1
        return result

    def _get_local_path(self, media_file: MediaFile) -> Path:
        """Determine local file path based on configuration"""
        base = self.config.storage.base_dir
        
        if self.config.storage.organize_by_channel:
            base = base / media_file.channel_id
        
        if self.config.storage.organize_by_date:
            date_str = datetime.fromtimestamp(int(media_file.timestamp) if media_file.timestamp.isdigit() else 0).strftime("%Y-%m-%d")
            base = base / date_str
        
        if self.config.storage.organize_by_sender:
            base = base / media_file.sender_name
        
        return base / media_file.filename

    def print_statistics(self) -> None:
        """Print download statistics"""
        logger.info(f"\n📊 Statistiken:")
        logger.info(f"  ✓ Heruntergeladen: {self.stats['downloaded']}")
        logger.info(f"  ⊘ Übersprungen: {self.stats['skipped']}")
        logger.info(f"  ✗ Fehler: {self.stats['errors']}")
        logger.info(f"  💾 Größe: {self.stats['total_size'] / 1024 / 1024:.2f} MB")
