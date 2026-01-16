"""EXIF metadata handling and manipulation."""
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


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
            
            image = PILImage.open(file_path)
            
            # Get EXIF data
            try:
                exif_dict = piexif.load(file_path)
            except (piexif.InvalidImageDataError, AttributeError):
                # No EXIF data, just save
                image.save(output_path, quality=95)
                return True
            
            # Sensitive fields to remove
            sensitive_fields = {
                '0th': [36867, 36868, 271, 272, 305, 306, 315, 33432],  # DateTime, Make, Model, Software, etc.
                'Exif': [36867, 36868, 37510, 37521, 37522, 41729, 41730, 42016, 42017],  # GPS, Serial, etc.
                '1st': [],
                'GPS': [0, 1, 2, 3, 4]  # All GPS tags
            }
            
            # Remove sensitive IFDs
            if 'GPS' in exif_dict:
                del exif_dict['GPS']
            
            # Sanitize other IFDs
            for ifd_name in ['0th', 'Exif', '1st']:
                if ifd_name in exif_dict:
                    for field_id in sensitive_fields.get(ifd_name, []):
                        if field_id in exif_dict[ifd_name]:
                            del exif_dict[ifd_name][field_id]
            
            # Save sanitized image
            exif_bytes = piexif.dump(exif_dict)
            image.save(output_path, exif=exif_bytes, quality=95)
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
