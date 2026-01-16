"""Extended database schema for metadata storage."""
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class MetadataDB:
    """Extended database for detailed metadata storage."""

    def __init__(self, db_path: Path):
        """Initialize metadata database."""
        self.db_path = db_path

    def initialize(self):
        """Create metadata tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Image metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS image_metadata (
                    file_id TEXT PRIMARY KEY,
                    camera_model TEXT,
                    creation_date TEXT,
                    dimensions TEXT,
                    exif_available BOOLEAN,
                    exif_sanitized BOOLEAN,
                    created_at TIMESTAMP
                )
            ''')

            # Video metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS video_metadata (
                    file_id TEXT PRIMARY KEY,
                    duration REAL,
                    video_codec TEXT,
                    audio_codec TEXT,
                    resolution TEXT,
                    fps REAL,
                    created_at TIMESTAMP
                )
            ''')

            # Create indices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_camera ON image_metadata(camera_model)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_creation_date ON image_metadata(creation_date)')

            conn.commit()
            logger.info("✓ Metadata database initialized")

    def save_image_metadata(self, file_id: str, metadata: Dict) -> bool:
        """Save image metadata.
        
        Args:
            file_id: File ID
            metadata: Metadata dictionary
            
        Returns:
            True if successful
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO image_metadata
                    (file_id, camera_model, creation_date, dimensions, exif_available, exif_sanitized, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    file_id,
                    metadata.get('camera_model'),
                    metadata.get('creation_date'),
                    metadata.get('dimensions'),
                    metadata.get('exif_available', False),
                    metadata.get('exif_sanitized', False)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving image metadata: {e}")
            return False

    def get_image_metadata(self, file_id: str) -> Optional[Dict]:
        """Get image metadata.
        
        Args:
            file_id: File ID
            
        Returns:
            Metadata dictionary or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT camera_model, creation_date, dimensions, exif_available, exif_sanitized
                    FROM image_metadata WHERE file_id = ?
                ''', (file_id,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'camera_model': row[0],
                        'creation_date': row[1],
                        'dimensions': row[2],
                        'exif_available': row[3],
                        'exif_sanitized': row[4]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting image metadata: {e}")
            return None

    def get_statistics_by_camera(self) -> Dict[str, int]:
        """Get file count by camera model.
        
        Returns:
            Dictionary with camera model and count
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT camera_model, COUNT(*) FROM image_metadata
                    WHERE camera_model IS NOT NULL
                    GROUP BY camera_model
                    ORDER BY COUNT(*) DESC
                ''')
                return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error getting camera statistics: {e}")
            return {}
