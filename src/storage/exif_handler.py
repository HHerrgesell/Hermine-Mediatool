"""EXIF metadata handling and manipulation."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

# EXIF tag IDs for Author/Artist field
EXIF_TAG_ARTIST = 315  # 0x013B - Artist (Author) tag in IFD0


class EXIFHandler:
    """Handle EXIF metadata in image files."""

    def __init__(self, preserve_exif: bool = True, remove_sensitive: bool = True):
        """Initialize EXIF handler.
        
        Args:
            preserve_exif: Keep EXIF data in downloaded files
            remove_sensitive: Remove sensitive EXIF data (GPS, camera model, etc.)
        """
        self.preserve_exif = preserve_exif
        self.remove_sensitive = remove_sensitive
        
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            self.Image = Image
            self.TAGS = TAGS
            self.pil_available = True
        except ImportError:
            logger.warning("Pillow nicht installiert - EXIF-Verarbeitung deaktiviert")
            self.pil_available = False

    def extract_exif(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extract EXIF data from image file.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dictionary with EXIF data or None if not available
        """
        if not self.pil_available:
            return None

        try:
            image = self.Image.open(file_path)
            exif_data = image._getexif()
            
            if not exif_data:
                return None
            
            exif_dict = {}
            for tag_id, value in exif_data.items():
                tag_name = self.TAGS.get(tag_id, tag_id)
                exif_dict[tag_name] = value
            
            logger.debug(f"✓ EXIF-Daten extrahiert: {file_path.name}")
            return exif_dict
            
        except Exception as e:
            logger.debug(f"Keine EXIF-Daten: {file_path.name} ({e})")
            return None

    def get_creation_datetime(self, file_path: Path) -> Optional[datetime]:
        """Extract creation datetime from EXIF data.

        Args:
            file_path: Path to image file

        Returns:
            Datetime object or None
        """
        if not self.pil_available:
            return None

        try:
            exif_data = self.extract_exif(file_path)
            if not exif_data:
                return None

            # Try different EXIF datetime fields
            for field in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                if field in exif_data:
                    dt_str = exif_data[field]
                    try:
                        return datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    except (ValueError, TypeError):
                        continue

            return None

        except Exception as e:
            logger.debug(f"Fehler beim Extrahieren der Datetime: {e}")
            return None

    def get_author(self, file_path: Path) -> Optional[str]:
        """Extract Author/Artist from EXIF data.

        Args:
            file_path: Path to image file

        Returns:
            Author string or None if not set
        """
        if not self.pil_available:
            return None

        try:
            exif_data = self.extract_exif(file_path)
            if not exif_data:
                return None

            # Check for Artist field (which is the Author in EXIF)
            author = exif_data.get('Artist')
            if author and isinstance(author, (str, bytes)):
                author_str = author.decode('utf-8') if isinstance(author, bytes) else author
                if author_str.strip():
                    return author_str.strip()

            return None

        except Exception as e:
            logger.debug(f"Fehler beim Extrahieren des Autors: {e}")
            return None

    def set_author(self, file_path: Path, author: str, output_path: Optional[Path] = None) -> bool:
        """Set Author/Artist field in EXIF data.

        Args:
            file_path: Path to source image
            author: Author name to set
            output_path: Path to save modified image (default: overwrite original)

        Returns:
            True if successful, False otherwise
        """
        if not self.pil_available:
            return False

        if output_path is None:
            output_path = file_path

        try:
            import piexif
            from PIL import Image as PILImage

            # Convert Path to string for piexif compatibility
            file_path_str = str(file_path)
            output_path_str = str(output_path)

            image = PILImage.open(file_path_str)

            # Try to load existing EXIF data
            try:
                exif_dict = piexif.load(file_path_str)
            except (piexif.InvalidImageDataError, AttributeError, KeyError):
                # No EXIF data exists, create new
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

            # Set Author/Artist field (tag 315 = 0x013B)
            # EXIF Artist field expects bytes
            author_bytes = author.encode('utf-8')
            exif_dict['0th'][EXIF_TAG_ARTIST] = author_bytes

            # Save image with updated EXIF
            exif_bytes = piexif.dump(exif_dict)
            image.save(output_path_str, exif=exif_bytes, quality=95)

            logger.info(f"✓ Author gesetzt: {author} in {file_path.name}")
            return True

        except ImportError:
            logger.warning("piexif nicht installiert - Author kann nicht gesetzt werden")
            return False
        except Exception as e:
            logger.warning(f"Fehler beim Setzen des Authors: {e}")
            return False

    def ensure_author(self, file_path: Path, author: str, output_path: Optional[Path] = None) -> Tuple[bool, bool]:
        """Check if Author exists in EXIF, set it if not.

        Args:
            file_path: Path to image file
            author: Author name to set if not present
            output_path: Path to save modified image (default: overwrite original)

        Returns:
            Tuple of (success, was_modified):
            - success: True if operation completed without errors
            - was_modified: True if Author was added (was missing)
        """
        try:
            existing_author = self.get_author(file_path)

            if existing_author:
                logger.debug(f"Author bereits vorhanden: {existing_author} in {file_path.name}")
                return (True, False)

            # Author not set, add it
            success = self.set_author(file_path, author, output_path)
            if success:
                logger.info(f"✓ Author hinzugefügt: {author} → {file_path.name}")
            return (success, success)

        except Exception as e:
            logger.warning(f"Fehler bei ensure_author: {e}")
            return (False, False)

    def remove_exif(self, file_path: Path, output_path: Optional[Path] = None) -> bool:
        """Remove all EXIF data from image file.
        
        Args:
            file_path: Path to source image
            output_path: Path to save cleaned image (default: overwrite original)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.pil_available:
            return False
        
        if output_path is None:
            output_path = file_path

        try:
            image = self.Image.open(file_path)
            
            # Create new image without EXIF
            data = list(image.getdata())
            image_without_exif = self.Image.new(image.mode, image.size)
            image_without_exif.putdata(data)
            
            # Save
            image_without_exif.save(output_path, quality=95)
            logger.debug(f"✓ EXIF-Daten entfernt: {file_path.name}")
            return True
            
        except Exception as e:
            logger.warning(f"Fehler beim Entfernen von EXIF-Daten: {e}")
            return False

    def sanitize_exif(self, file_path: Path, output_path: Optional[Path] = None) -> bool:
        """Remove sensitive EXIF data from image file.

        Keeps useful metadata (date, camera model) but removes:
        - GPS coordinates
        - Camera serial number
        - Software version
        - Copyright info
        - User comments

        Note: Author/Artist field (315) is preserved for attribution.

        Args:
            file_path: Path to source image
            output_path: Path to save sanitized image

        Returns:
            True if successful, False otherwise
        """
        if not self.pil_available:
            return False

        if output_path is None:
            output_path = file_path

        try:
            from PIL import Image as PILImage
            import piexif

            # Convert Path to string for piexif compatibility
            file_path_str = str(file_path)
            output_path_str = str(output_path)

            image = PILImage.open(file_path_str)

            # Get EXIF data
            try:
                exif_dict = piexif.load(file_path_str)
            except (piexif.InvalidImageDataError, AttributeError, KeyError):
                # No EXIF data, just save
                image.save(output_path_str, quality=95)
                return True

            # Sensitive fields to remove
            # Note: 315 (Artist/Author) is intentionally NOT removed - we preserve it for attribution
            sensitive_fields = {
                '0th': [271, 272, 305, 306, 33432],  # Make, Model, Software, DateTime, Copyright (NOT Artist/315)
                'Exif': [37510, 37521, 37522, 42016, 42017],  # UserComment, SerialNumber, etc.
                '1st': [],
            }

            # Remove GPS data entirely
            if 'GPS' in exif_dict:
                exif_dict['GPS'] = {}

            # Sanitize other IFDs - remove sensitive fields but keep Author
            for ifd_name in ['0th', 'Exif', '1st']:
                if ifd_name in exif_dict and isinstance(exif_dict[ifd_name], dict):
                    for field_id in sensitive_fields.get(ifd_name, []):
                        if field_id in exif_dict[ifd_name]:
                            del exif_dict[ifd_name][field_id]

            # Save sanitized image
            exif_bytes = piexif.dump(exif_dict)
            image.save(output_path_str, exif=exif_bytes, quality=95)
            logger.debug(f"✓ EXIF-Daten bereinigt: {file_path.name}")
            return True

        except ImportError:
            logger.warning("piexif nicht installiert - vollständiges Sanitizing nicht möglich")
            return self.remove_exif(file_path, output_path)
        except Exception as e:
            logger.warning(f"Fehler beim Bereinigen von EXIF-Daten: {e}")
            return False

    @staticmethod
    def get_sensitive_exif_fields() -> Dict[str, list]:
        """Get list of sensitive EXIF fields.
        
        Returns:
            Dictionary with sensitive field names
        """
        return {
            'GPS': [
                'GPSInfo',
                'GPSLatitude',
                'GPSLongitude',
                'GPSAltitude',
            ],
            'Camera': [
                'SerialNumber',
                'InternalSerialNumber',
                'LensModel',
                'CameraOwnerName',
            ],
            'Software': [
                'Software',
                'ProcessingSoftware',
                'ApplicationRecordVersion',
            ],
            'User': [
                'UserComment',
                'ImageDescription',
                'Copyright',
                'Artist',
            ]
        }
