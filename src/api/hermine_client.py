"""Hermine API Client"""
import logging
import asyncio
import random
import string
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

        # Generate device ID
        self.device_id = "".join(random.choice(string.ascii_letters + string.digits)
                                for _ in range(32))
        self.client_key = None
        self.user_id = None
        self.hidden_id = None

        # Set headers matching reference implementation
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.5",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 ("
                          "KHTML, like Gecko) Chrome/97.0.4692.99 Mobile Safari/537.36",
        })

        self._authenticate()

    def _post(self, url: str, data: Dict[str, Any], include_auth: bool = True) -> Dict[str, Any]:
        """Make POST request to API"""
        data["device_id"] = self.device_id
        if include_auth and self.client_key:
            data["client_key"] = self.client_key

        response = self.session.post(
            f"{self.base_url}/{url}",
            data=data,
            timeout=self.timeout,
            verify=self.verify_ssl
        )
        response.raise_for_status()

        resp_data = response.json()
        if resp_data.get("status", {}).get("value") != "OK":
            raise ValueError(resp_data.get("status", {}).get("message", "Unknown error"))
        return resp_data.get("payload", {})

    def _authenticate(self) -> None:
        """Authenticate against Hermine API"""
        try:
            data = self._post("auth/login", {
                "email": self.username,
                "password": self.password,
                "app_name": "hermine@thw-Chrome:97.0.4692.99-browser-4.11.1",
                "encrypted": True,
                "callable": True,
            }, include_auth=False)

            self.client_key = data["client_key"]
            self.user_id = data["userinfo"]["id"]
            self.hidden_id = data["userinfo"]["socket_id"]

            logger.info(f"✓ Authentifiziert als {self.username}")

        except (RequestException, ValueError) as e:
            logger.error(f"✗ Authentifizierung fehlgeschlagen: {e}")
            raise

    def get_companies(self) -> List[Dict[str, Any]]:
        """Get list of companies"""
        try:
            data = self._post("company/member", {"no_cache": True})
            companies = data.get("companies", [])
            logger.info(f"✓ {len(companies)} Unternehmen gefunden")
            return companies
        except (RequestException, ValueError) as e:
            logger.error(f"✗ Fehler beim Abrufen von Unternehmen: {e}")
            raise

    def get_channels(self, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available channels"""
        try:
            # If no company_id provided, get first company
            if company_id is None:
                companies = self.get_companies()
                if not companies:
                    logger.warning("Keine Unternehmen gefunden")
                    return []
                company_id = companies[0]["id"]

            data = self._post("channels/subscripted", {"company": company_id})
            channels = data.get("channels", [])
            logger.info(f"✓ {len(channels)} Kanäle gefunden")
            return channels
        except (RequestException, ValueError) as e:
            logger.error(f"✗ Fehler beim Abrufen von Kanälen: {e}")
            raise

    async def get_media_files(self, channel_id: str, limit: int = 30) -> List[MediaFile]:
        """Get all media files from a channel"""
        media_files = []
        offset = 0

        try:
            while True:
                data = self._post("message/content", {
                    "channel_id": channel_id,
                    "source": "channel",
                    "limit": limit,
                    "offset": offset,
                })

                messages = data.get("messages", [])

                # Debug: log first message structure
                if messages and offset == 0:
                    logger.debug(f"First message structure: {messages[0].keys() if messages else 'no messages'}")
                    if messages and len(messages) > 0:
                        msg = messages[0]
                        logger.debug(f"Message keys: {msg.keys()}")
                        logger.debug(f"Files field: {msg.get('files', 'NO FILES FIELD')}")
                        logger.debug(f"Kind field: {msg.get('kind', 'NO KIND FIELD')}")

                if not messages:
                    break

                logger.debug(f"Processing {len(messages)} messages at offset {offset}")

                for msg in messages:
                    # Check if message has files
                    files = msg.get("files", [])
                    if files:
                        logger.debug(f"Found {len(files)} files in message {msg.get('id')}")
                        for file_info in files:
                            # The API uses "mime" not "type"
                            mime_type = file_info.get("mime", "")
                            logger.debug(f"File: {file_info.get('name')}, mime: {mime_type}")
                            if self._is_media_file(mime_type):
                                # Store file_id directly (not full URL)
                                file_id = file_info.get("id")
                                download_url = str(file_id)  # Just store the ID

                                # Get sender info from sender object
                                sender = msg.get("sender", {})
                                sender_name = f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip() or "Unknown"

                                # Get file size in bytes
                                file_size = int(file_info.get("size_byte", 0))

                                media_files.append(MediaFile(
                                    file_id=str(file_id),
                                    filename=file_info.get("name", ""),
                                    mime_type=mime_type,
                                    size=file_size,
                                    channel_id=channel_id,
                                    message_id=str(msg.get("id", "")),
                                    sender_id=str(sender.get("id", "")),
                                    sender_name=sender_name,
                                    download_url=download_url,
                                    timestamp=str(msg.get("time", ""))
                                ))
                            else:
                                logger.debug(f"Skipping non-media file: {mime_type}")

                offset += limit
                await asyncio.sleep(0.1)  # Rate limiting

            logger.info(f"✓ {len(media_files)} Mediadateien in Kanal {channel_id}")
            return media_files

        except (RequestException, ValueError) as e:
            logger.error(f"✗ Fehler beim Abrufen von Mediadateien: {e}")
            raise

    async def download_file(self, file_id: str, timeout: int = None) -> bytes:
        """Download a file by ID"""
        try:
            # Use POST with form data including file_id
            data = {
                "device_id": self.device_id,
                "client_key": self.client_key,
                "id": file_id  # Submit the file ID as a form parameter
            }

            download_url = f"{self.base_url}/file/download"
            response = self.session.post(
                download_url,
                data=data,
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
