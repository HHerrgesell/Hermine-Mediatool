"""SQLite Database for download manifest and deduplication"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ManifestDB:
    """SQLite Manifest Database"""

    def __init__(self, db_path: Path):
        """Initialize database"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = None
        self._connect()

    def _connect(self) -> None:
        """Connect to database"""
        try:
            self.connection = sqlite3.connect(str(self.db_path))
            self.connection.row_factory = sqlite3.Row
            logger.info(f"✓ Manifest DB verbunden: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"✗ DB-Verbindung fehlgeschlagen: {e}")
            raise

    def initialize(self) -> None:
        """Initialize database schema"""
        try:
            cursor = self.connection.cursor()
            
            # Downloaded files table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloaded_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_hash TEXT,
                    file_size INTEGER,
                    mime_type TEXT,
                    sender TEXT,
                    local_path TEXT,
                    nextcloud_path TEXT,
                    download_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed'
                )
            ''')
            
            # Error log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    last_attempt DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_id) REFERENCES downloaded_files(file_id)
                )
            ''')
            
            # Channels metadata table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT UNIQUE NOT NULL,
                    channel_name TEXT,
                    last_sync DATETIME,
                    file_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON downloaded_files(file_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_channel_id ON downloaded_files(channel_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender ON downloaded_files(sender)')
            
            self.connection.commit()
            logger.info("✓ Manifest DB Schema initialisiert")
            
        except sqlite3.Error as e:
            logger.error(f"✗ DB-Initialisierung fehlgeschlagen: {e}")
            raise

    def file_exists(self, file_id: str) -> bool:
        """Check if file already downloaded"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT 1 FROM downloaded_files WHERE file_id = ?', (file_id,))
            return cursor.fetchone() is not None
        except sqlite3.Error as e:
            logger.error(f"✗ DB-Abfrage fehlgeschlagen: {e}")
            return False

    def insert_file(self, file_id: str, channel_id: str, message_id: str, 
                   filename: str, file_hash: Optional[str], file_size: int,
                   mime_type: str, sender: str, local_path: Optional[str] = None,
                   nextcloud_path: Optional[str] = None) -> None:
        """Insert downloaded file record"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO downloaded_files 
                (file_id, channel_id, message_id, filename, file_hash, file_size, 
                 mime_type, sender, local_path, nextcloud_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, channel_id, message_id, filename, file_hash, file_size,
                   mime_type, sender, local_path, nextcloud_path))
            self.connection.commit()
        except sqlite3.Error as e:
            logger.error(f"✗ Datensatz-Insert fehlgeschlagen: {e}")
            raise

    def record_error(self, file_id: str, error_message: str) -> None:
        """Record download error"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                INSERT INTO download_errors (file_id, error_message, retry_count)
                VALUES (?, ?, 1)
            ''', (file_id, error_message))
            self.connection.commit()
        except sqlite3.Error as e:
            logger.error(f"✗ Fehlerprotokoll-Insert fehlgeschlagen: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            cursor = self.connection.cursor()
            
            cursor.execute('SELECT COUNT(*) as count, SUM(file_size) as total_size FROM downloaded_files')
            row = cursor.fetchone()
            
            return {
                'total_files': row['count'] or 0,
                'total_size': row['total_size'] or 0,
                'total_errors': self._count_errors()
            }
        except sqlite3.Error as e:
            logger.error(f"✗ Statistik-Abfrage fehlgeschlagen: {e}")
            return {'total_files': 0, 'total_size': 0, 'total_errors': 0}

    def _count_errors(self) -> int:
        """Count total errors"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM download_errors')
            row = cursor.fetchone()
            return row['count'] or 0
        except sqlite3.Error:
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics (alias for get_stats with more details)"""
        try:
            cursor = self.connection.cursor()

            # Basic stats
            cursor.execute('SELECT COUNT(*) as count, SUM(file_size) as total_size FROM downloaded_files')
            row = cursor.fetchone()

            # Count unique channels
            cursor.execute('SELECT COUNT(DISTINCT channel_id) as channels FROM downloaded_files')
            channels_row = cursor.fetchone()

            # Count unique senders
            cursor.execute('SELECT COUNT(DISTINCT sender) as senders FROM downloaded_files')
            senders_row = cursor.fetchone()

            return {
                'total_files': row['count'] or 0,
                'total_size': row['total_size'] or 0,
                'channels': channels_row['channels'] or 0,
                'senders': senders_row['senders'] or 0,
                'errors': self._count_errors()
            }
        except sqlite3.Error as e:
            logger.error(f"✗ Statistik-Abfrage fehlgeschlagen: {e}")
            return {'total_files': 0, 'total_size': 0, 'channels': 0, 'senders': 0, 'errors': 0}

    def get_files_by_channel(self) -> Dict[str, int]:
        """Get file counts by channel"""
        try:
            cursor = self.connection.cursor()
            cursor.execute('''
                SELECT channel_id, COUNT(*) as count
                FROM downloaded_files
                GROUP BY channel_id
            ''')
            return {row['channel_id']: row['count'] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"✗ Kanal-Statistik fehlgeschlagen: {e}")
            return {}

    def get_files_by_sender(self, channel_id: Optional[str] = None) -> Dict[str, int]:
        """Get file counts by sender"""
        try:
            cursor = self.connection.cursor()
            if channel_id:
                cursor.execute('''
                    SELECT sender, COUNT(*) as count
                    FROM downloaded_files
                    WHERE channel_id = ?
                    GROUP BY sender
                ''', (channel_id,))
            else:
                cursor.execute('''
                    SELECT sender, COUNT(*) as count
                    FROM downloaded_files
                    GROUP BY sender
                ''')
            return {row['sender']: row['count'] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            logger.error(f"✗ Absender-Statistik fehlgeschlagen: {e}")
            return {}

    def get_all_files(self, limit: int = 100, offset: int = 0,
                      search: Optional[str] = None,
                      channel_id: Optional[str] = None,
                      sender: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all downloaded files with optional filtering.

        Args:
            limit: Maximum number of files to return
            offset: Offset for pagination
            search: Search term for filename
            channel_id: Filter by channel
            sender: Filter by sender

        Returns:
            List of file records as dictionaries
        """
        try:
            cursor = self.connection.cursor()

            query = 'SELECT * FROM downloaded_files WHERE 1=1'
            params = []

            if search:
                query += ' AND (filename LIKE ? OR sender LIKE ?)'
                search_term = f'%{search}%'
                params.extend([search_term, search_term])

            if channel_id:
                query += ' AND channel_id = ?'
                params.append(channel_id)

            if sender:
                query += ' AND sender = ?'
                params.append(sender)

            query += ' ORDER BY download_timestamp DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        except sqlite3.Error as e:
            logger.error(f"✗ Datei-Abfrage fehlgeschlagen: {e}")
            return []

    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get a single file by its file_id.

        Args:
            file_id: The file ID to look up

        Returns:
            File record as dictionary or None
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT * FROM downloaded_files WHERE file_id = ?', (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"✗ Datei-Abfrage fehlgeschlagen: {e}")
            return None

    def delete_file_record(self, file_id: str) -> bool:
        """Delete a file record from the database (allows re-download).

        Args:
            file_id: The file ID to delete

        Returns:
            True if deleted, False otherwise
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute('DELETE FROM downloaded_files WHERE file_id = ?', (file_id,))
            self.connection.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"✓ Datensatz gelöscht: {file_id}")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"✗ Datensatz-Löschung fehlgeschlagen: {e}")
            return False

    def count_files(self, search: Optional[str] = None,
                    channel_id: Optional[str] = None,
                    sender: Optional[str] = None) -> int:
        """Count files with optional filtering.

        Args:
            search: Search term for filename
            channel_id: Filter by channel
            sender: Filter by sender

        Returns:
            Total count of matching files
        """
        try:
            cursor = self.connection.cursor()

            query = 'SELECT COUNT(*) as count FROM downloaded_files WHERE 1=1'
            params = []

            if search:
                query += ' AND (filename LIKE ? OR sender LIKE ?)'
                search_term = f'%{search}%'
                params.extend([search_term, search_term])

            if channel_id:
                query += ' AND channel_id = ?'
                params.append(channel_id)

            if sender:
                query += ' AND sender = ?'
                params.append(sender)

            cursor.execute(query, params)
            row = cursor.fetchone()
            return row['count'] or 0

        except sqlite3.Error as e:
            logger.error(f"✗ Zähl-Abfrage fehlgeschlagen: {e}")
            return 0

    def get_unique_channels(self) -> List[str]:
        """Get list of unique channel IDs."""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT DISTINCT channel_id FROM downloaded_files ORDER BY channel_id')
            return [row['channel_id'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"✗ Kanal-Abfrage fehlgeschlagen: {e}")
            return []

    def get_unique_senders(self) -> List[str]:
        """Get list of unique senders."""
        try:
            cursor = self.connection.cursor()
            cursor.execute('SELECT DISTINCT sender FROM downloaded_files ORDER BY sender')
            return [row['sender'] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"✗ Absender-Abfrage fehlgeschlagen: {e}")
            return []

    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("DB-Verbindung geschlossen")
