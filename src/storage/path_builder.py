"""Path builder for organizing downloaded files."""
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import re

logger = logging.getLogger(__name__)


class PathBuilder:
    """Build file paths based on configurable template."""

    PLACEHOLDER_PATTERN = r'{([^}]+)}'
    AVAILABLE_PLACEHOLDERS = {
        'year': 'Jahreszahl (YYYY)',
        'month': 'Monatszahl (1-12)',
        'month:02d': 'Monatszahl mit führender Null (01-12)',
        'day': 'Tagesszahl (1-31)',
        'day:02d': 'Tagesszahl mit führender Null (01-31)',
        'sender': 'Absender-Name (gekürzt)',
        'filename': 'Original-Dateiname',
        'channel_name': 'Kanal-Name'
    }

    @staticmethod
    def build_path(
        base_dir: Path,
        template: str,
        filename: str,
        sender_name: Optional[str] = None,
        channel_name: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> Path:
        """Build file path from template."""
        if timestamp is None:
            timestamp = datetime.now()

        # Sanitize sender name
        sender_safe = PathBuilder._sanitize_name(sender_name or 'Unknown')
        channel_safe = PathBuilder._sanitize_name(channel_name or 'Unknown')
        filename_safe = PathBuilder._sanitize_filename(filename)

        # Replace placeholders
        path_str = template
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

        # Combine with base directory
        full_path = base_dir / path_str

        # Create parent directories
        full_path.parent.mkdir(parents=True, exist_ok=True)

        return full_path

    @staticmethod
    def _sanitize_name(name: str, max_length: int = 50) -> str:
        """Sanitize name for use in file paths."""
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        name = re.sub(r'\s+', '_', name)
        # Remove leading/trailing dots and spaces
        name = name.strip('. ')
        # Limit length
        if len(name) > max_length:
            name = name[:max_length]
        return name or 'unnamed'

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Sanitize filename."""
        # Remove path components
        filename = Path(filename).name
        # Remove invalid characters
        filename = re.sub(r'[<>:"|?*]', '', filename)
        # Limit length (keeping extension)
        if len(filename) > 200:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:193] + ('.' + ext if ext else '')
        return filename or 'unnamed.bin'

    @staticmethod
    def get_template_help() -> str:
        """Get help text for path templates."""
        help_text = "\n📋 Verfügbare Template-Platzhalter:\n\n"
        help_text += "Standard-Template: {year}/{month:02d}/{sender}_{filename}\n\n"
        
        for placeholder, description in PathBuilder.AVAILABLE_PLACEHOLDERS.items():
            help_text += f"  • {{{placeholder:15s}}} - {description}\n"
        
        help_text += "\n📝 Beispiele:\n"
        help_text += "  {year}/{month:02d}/{sender}_{filename}\n"
        help_text += "  {channel_name}/{year}/{month:02d}/{filename}\n"
        help_text += "  {sender}/{year}/{filename}\n"
        
        return help_text
