"""EXIF data processing during downloads."""
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.storage.exif_handler import EXIFHandler

logger = logging.getLogger(__name__)


class EXIFProcessor:
    """Process EXIF data for downloaded files."""

    def __init__(self, config):
        """Initialize EXIF processor.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.exif_handler = EXIFHandler(
            preserve_exif=config.storage.create_manifest,
            remove_sensitive=True
        )

    def process_file(self, file_path: Path, preserve_timestamp: bool = True,
                     sender_name: Optional[str] = None) -> bool:
        """Process EXIF data in downloaded file.

        Args:
            file_path: Path to downloaded file
            preserve_timestamp: Extract and preserve creation timestamp
            sender_name: Uploader's full name to set as Author if not present

        Returns:
            True if successful or not applicable, False on error
        """
        try:
            # Only process image files
            if not self._is_image(file_path):
                return True

            logger.debug(f"Processing EXIF for: {file_path.name}")

            # Extract metadata before processing
            exif_data = self.exif_handler.extract_exif(file_path)
            creation_dt = None

            if preserve_timestamp and exif_data:
                creation_dt = self.exif_handler.get_creation_datetime(file_path)

            # Check and set Author field from sender_name if not present
            if sender_name:
                success, was_modified = self.exif_handler.ensure_author(file_path, sender_name)
                if was_modified:
                    logger.debug(f"✓ Author set to: {sender_name}")

            # Remove sensitive data (but keep Author!)
            if self.config.storage.extract_metadata:
                success = self.exif_handler.sanitize_exif(file_path)
                if success:
                    logger.debug(f"✓ EXIF sanitized: {file_path.name}")
                else:
                    logger.debug(f"Could not sanitize EXIF: {file_path.name}")

            # Restore timestamp if needed
            if preserve_timestamp and creation_dt:
                self._restore_timestamp(file_path, creation_dt)

            return True

        except Exception as e:
            logger.error(f"Error processing EXIF: {e}")
            return False

    def extract_metadata_for_db(self, file_path: Path) -> dict:
        """Extract EXIF metadata for database storage.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with extracted metadata
        """
        metadata = {
            'camera_model': None,
            'creation_date': None,
            'dimensions': None,
            'exif_available': False
        }
        
        try:
            if not self._is_image(file_path):
                return metadata
            
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            image = Image.open(file_path)
            
            # Image dimensions
            metadata['dimensions'] = f"{image.width}x{image.height}"
            
            # EXIF data
            try:
                exif_data = image._getexif()
                if exif_data:
                    metadata['exif_available'] = True
                    
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        
                        if tag_name == 'Model' and isinstance(value, (str, bytes)):
                            metadata['camera_model'] = str(value)
                        elif tag_name == 'DateTime' and isinstance(value, str):
                            try:
                                metadata['creation_date'] = datetime.strptime(
                                    value, '%Y:%m:%d %H:%M:%S'
                                ).isoformat()
                            except ValueError:
                                pass
            except (AttributeError, TypeError):
                pass
            
            return metadata
            
        except Exception as e:
            logger.debug(f"Error extracting metadata: {e}")
            return metadata

    @staticmethod
    def _is_image(file_path: Path) -> bool:
        """Check if file is an image.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if image file
        """
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        return file_path.suffix.lower() in image_extensions

    @staticmethod
    def _restore_timestamp(file_path: Path, creation_dt: datetime):
        """Restore file modification timestamp from EXIF.
        
        Args:
            file_path: Path to file
            creation_dt: Creation datetime from EXIF
        """
        try:
            import os
            timestamp = creation_dt.timestamp()
            os.utime(file_path, (timestamp, timestamp))
            logger.debug(f"✓ Timestamp restored: {file_path.name}")
        except Exception as e:
            logger.debug(f"Could not restore timestamp: {e}")
