"""Hermine API Client"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

logger = logging.getLogger(__name__)


@dataclass
class MediaFile:
    """Represents a media file from Hermine"""
    file_id: str
    filename: str
    mime_type: str
    size: int
    channel_id: str
    message_id: str
    sender_id: str
    sender_name: str
    download_url: str
    timestamp: str


class HermineClient:
    """Hermine/Stashcat API Client"""

    def __init__(self, base_url: str, username: str, password: str, 
                 timeout: int = 30, verify_ssl: bool = True):
        """Initialize Hermine client"""
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.token = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate against Hermine API"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"username": self.username, "password": self.password},
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            data = response.json()
            self.token = data.get('token') or data.get('access_token')
            
            if not self.token:
                raise ValueError("No token in authentication response")
            
            self.session.headers.update({
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            })
            logger.info(f"✓ Authentifiziert als {self.username}")
            
        except (RequestException, ValueError) as e:
            logger.error(f"✗ Authentifizierung fehlgeschlagen: {e}")
            raise

    def get_channels(self) -> List[Dict[str, Any]]:
        """List all available channels"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/channels",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            channels = response.json().get('channels', [])
            logger.info(f"✓ {len(channels)} Kanäle gefunden")
            return channels
        except RequestException as e:
            logger.error(f"✗ Fehler beim Abrufen von Kanälen: {e}")
            raise

    async def get_media_files(self, channel_id: str, limit: int = 100) -> List[MediaFile]:
        """Get all media files from a channel"""
        media_files = []
        offset = 0
        
        try:
            while True:
                response = self.session.get(
                    f"{self.base_url}/api/v1/channels/{channel_id}/messages",
                    params={'limit': limit, 'offset': offset},
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                messages = response.json().get('messages', [])
                
                if not messages:
                    break
                
                for msg in messages:
                    attachments = msg.get('attachments', [])
                    for att in attachments:
                        mime_type = att.get('mime_type', '')
                        if self._is_media_file(mime_type):
                            media_files.append(MediaFile(
                                file_id=att.get('id'),
                                filename=att.get('filename'),
                                mime_type=mime_type,
                                size=att.get('size', 0),
                                channel_id=channel_id,
                                message_id=msg.get('id'),
                                sender_id=msg.get('sender_id', ''),
                                sender_name=msg.get('sender_name', 'Unknown'),
                                download_url=att.get('download_url'),
                                timestamp=msg.get('timestamp', '')
                            ))
                
                offset += limit
                await asyncio.sleep(0.1)  # Rate limiting
            
            logger.info(f"✓ {len(media_files)} Mediadateien in Kanal {channel_id}")
            return media_files
            
        except RequestException as e:
            logger.error(f"✗ Fehler beim Abrufen von Mediadateien: {e}")
            raise

    async def download_file(self, url: str, timeout: int = None) -> bytes:
        """Download a file from URL"""
        try:
            response = self.session.get(
                url,
                timeout=timeout or self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            response.raise_for_status()
            return response.content
        except RequestException as e:
            logger.error(f"✗ Download fehlgeschlagen: {e}")
            raise

    @staticmethod
    def _is_media_file(mime_type: str) -> bool:
        """Check if MIME type is a media file"""
        media_prefixes = ('image/', 'video/', 'audio/')
        return any(mime_type.startswith(p) for p in media_prefixes)
