"""Hermine API client."""
import logging
import requests
from typing import List, Optional, Iterator
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import Channel, Message, MediaFile

logger = logging.getLogger(__name__)


class HermineClient:
    """Client for Hermine API"""

    def __init__(self, base_url: str, username: str, password: str,
                 timeout: int = 30, verify_ssl: bool = True):
        """Initialize Hermine client."""
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl

        self.session = requests.Session()
        self._setup_retry_strategy()
        self._authenticate()

    def _setup_retry_strategy(self):
        """Setup retry strategy for failed requests."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _authenticate(self):
        """Authenticate with Hermine."""
        try:
            # Try to get token or establish session
            auth = (self.username, self.password)
            response = self.session.get(
                f"{self.base_url}/api/me",
                auth=auth,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            logger.info("✓ Hermine API Authentication successful")
            self.session.auth = auth
        except Exception as e:
            raise Exception(f"Hermine authentication failed: {e}")

    def get_channels(self) -> List[Channel]:
        """Fetch all available channels."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/channels",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            data = response.json()

            channels = []
            for item in data.get('channels', []):
                channel = Channel(
                    id=item.get('id'),
                    name=item.get('name'),
                    description=item.get('description'),
                    member_count=item.get('member_count', 0),
                    created_at=self._parse_datetime(item.get('created_at')),
                    updated_at=self._parse_datetime(item.get('updated_at'))
                )
                channels.append(channel)

            logger.debug(f"Fetched {len(channels)} channels")
            return channels
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            raise

    def stream_all_messages(self, channel_id: str, batch_size: int = 50) -> Iterator[Message]:
        """Stream all messages from a channel."""
        offset = 0
        while True:
            try:
                response = self.session.get(
                    f"{self.base_url}/api/channels/{channel_id}/messages",
                    params={'offset': offset, 'limit': batch_size},
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                data = response.json()

                messages = data.get('messages', [])
                if not messages:
                    break

                for item in messages:
                    message = Message(
                        id=item.get('id'),
                        channel_id=channel_id,
                        sender_id=item.get('sender_id'),
                        sender_name=item.get('sender_name'),
                        content=item.get('content', ''),
                        created_at=self._parse_datetime(item.get('created_at')),
                        attachments=item.get('attachments', [])
                    )
                    yield message

                offset += batch_size
            except Exception as e:
                logger.error(f"Error streaming messages: {e}")
                break

    def get_media_files(self, channel_id: str, message_id: str) -> List[MediaFile]:
        """Get media files from a message."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/channels/{channel_id}/messages/{message_id}/media",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            data = response.json()

            files = []
            for item in data.get('media', []):
                media_file = MediaFile(
                    id=item.get('id'),
                    filename=item.get('filename'),
                    size=item.get('size', 0),
                    mimetype=item.get('mimetype', 'application/octet-stream'),
                    url=item.get('url'),
                    message_id=message_id,
                    channel_id=channel_id,
                    sender_id=item.get('sender_id'),
                    sender_name=item.get('sender_name'),
                    created_at=self._parse_datetime(item.get('created_at'))
                )
                files.append(media_file)

            return files
        except Exception as e:
            logger.error(f"Failed to get media files: {e}")
            return []

    def download_file(self, file_id: str, channel_id: str) -> Optional[bytes]:
        """Download a file from Hermine."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/channels/{channel_id}/media/{file_id}/download",
                timeout=self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            raise

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from API."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except Exception:
            return None
