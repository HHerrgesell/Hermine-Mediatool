"""SQLite database for tracking downloaded files."""
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib

logger = logging.getLogger(__name__)


class ManifestDB:
    """SQLite manifest database for file tracking."""

    def __init__(self, db_path: Path):
        """Initialize database."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Files table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    size INTEGER,
                    mimetype TEXT,
                    checksum TEXT,
                    channel_id TEXT,
                    channel_name TEXT,
                    sender_id TEXT,
                    sender_name TEXT,
                    message_id TEXT,
                    downloaded_at TIMESTAMP,
                    created_at TIMESTAMP
                )
            ''')

            # Index for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_id ON files(id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_checksum ON files(checksum)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel ON files(channel_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender ON files(sender_id)')

            # Errors table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT,
                    error_message TEXT,
                    error_type TEXT,
                    attempt INTEGER,
                    timestamp TIMESTAMP
                )
            ''')

            conn.commit()
            logger.info("✓ Datenbank initialisiert")

    def file_exists(self, file_id: str) -> bool:
        """Check if file is already downloaded."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM files WHERE id = ?', (file_id,))
            return cursor.fetchone() is not None

    def checksum_exists(self, checksum: str) -> bool:
        """Check if file with same checksum was already downloaded."""
        if not checksum:
            return False
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM files WHERE checksum = ?', (checksum,))
            return cursor.fetchone() is not None

    def add_file(
        self,
        file_id: str,
        filename: str,
        file_path: str,
        size: int,
        mimetype: str,
        channel_id: str,
        channel_name: str,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        message_id: Optional[str] = None,
        checksum: Optional[str] = None
    ) -> bool:
        """Add file to manifest."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO files (
                        id, filename, file_path, size, mimetype, checksum,
                        channel_id, channel_name, sender_id, sender_name,
                        message_id, downloaded_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_id, filename, file_path, size, mimetype, checksum,
                    channel_id, channel_name, sender_id, sender_name,
                    message_id, datetime.now().isoformat(), datetime.now().isoformat()
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen zu Manifest: {e}")
            return False

    def add_error(self, file_id: str, error_message: str, error_type: str = 'download', attempt: int = 1):
        """Log download error."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO errors (file_id, error_message, error_type, attempt, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (file_id, error_message, error_type, attempt, datetime.now().isoformat()))
                conn.commit()
        except Exception as e:
            logger.error(f"Fehler beim Protokollieren von Fehler: {e}")

    def get_statistics(self) -> Dict:
        """Get download statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total files and size
            cursor.execute('SELECT COUNT(*), SUM(size) FROM files')
            total_files, total_size = cursor.fetchone()
            total_size = total_size or 0

            # Channels
            cursor.execute('SELECT COUNT(DISTINCT channel_id) FROM files')
            channels = cursor.fetchone()[0]

            # Senders
            cursor.execute('SELECT COUNT(DISTINCT sender_id) FROM files')
            senders = cursor.fetchone()[0]

            # Errors
            cursor.execute('SELECT COUNT(DISTINCT file_id) FROM errors')
            errors = cursor.fetchone()[0]

            return {
                'total_files': total_files or 0,
                'total_size': total_size,
                'channels': channels,
                'senders': senders,
                'errors': errors
            }

    def get_files_by_channel(self) -> Dict[str, int]:
        """Get file count by channel."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT channel_id, COUNT(*) FROM files
                GROUP BY channel_id
                ORDER BY COUNT(*) DESC
            ''')
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_files_by_sender(self, channel_id: Optional[str] = None) -> Dict[str, int]:
        """Get file count by sender."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if channel_id:
                cursor.execute('''
                    SELECT sender_name, COUNT(*) FROM files
                    WHERE channel_id = ?
                    GROUP BY sender_name
                    ORDER BY COUNT(*) DESC
                ''', (channel_id,))
            else:
                cursor.execute('''
                    SELECT sender_name, COUNT(*) FROM files
                    GROUP BY sender_name
                    ORDER BY COUNT(*) DESC
                ''')
            return {row[0]: row[1] for row in cursor.fetchall()}
