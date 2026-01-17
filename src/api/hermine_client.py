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
    encrypted: bool = False
    e2e_iv: str = ""
    file_key: str = ""
    file_iv: str = ""
    chat_key: str = ""
    base_64_data: str = ""  # Encrypted file data embedded in message response


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
        self._private_key_cache = None

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

    def _get_private_key(self) -> str:
        """Get user's private RSA key from API (cached)"""
        if self._private_key_cache:
            return self._private_key_cache

        try:
            data = self._post("security/get_private_key", {})

            # Log all available fields to understand response structure
            logger.debug(f"Private key response fields: {list(data.keys())}")

            private_key = data.get("private_key", "")

            # Check if key is empty and log response size
            if not private_key or private_key.strip() == "":
                logger.error("Private key is empty!")
                logger.debug(f"Full response data keys: {data.keys()}")
                # Try alternative field names
                for key_name in ["privateKey", "key", "rsa_key", "encrypted_private_key"]:
                    if key_name in data:
                        logger.debug(f"Found alternative key field: {key_name}")
                        private_key = data.get(key_name, "")
                        break

            if not private_key:
                raise ValueError("No private key found in API response. User may need to generate keys in the app first.")

            # Log key format for debugging
            key_length = len(private_key)
            key_start = private_key[:50] if len(private_key) > 50 else private_key
            logger.debug(f"Private key length: {key_length}, starts with: {key_start[:30]}...")

            # Check if key needs PEM formatting
            if not private_key.startswith("-----BEGIN"):
                logger.debug("Private key doesn't have PEM headers, adding them")
                # Wrap in PEM format - try RSA PRIVATE KEY first
                private_key = f"-----BEGIN RSA PRIVATE KEY-----\n{private_key}\n-----END RSA PRIVATE KEY-----"

            self._private_key_cache = private_key
            logger.debug("✓ Private key retrieved and formatted")
            return self._private_key_cache
        except (RequestException, ValueError) as e:
            logger.error(f"✗ Failed to get private key: {e}")
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
                                # Construct download URL for app.thw-messenger.de
                                # Pattern from browser: https://app.thw-messenger.de/thw/app.thw-messenger.de/{file_id}/{filename}
                                file_id = file_info.get("id")
                                filename = file_info.get("name", "")

                                # Files are hosted on app subdomain with this specific path pattern
                                download_url = f"https://app.thw-messenger.de/thw/app.thw-messenger.de/{file_id}/{filename}"

                                logger.debug(f"File ID: {file_id}, filename: {filename}")
                                logger.debug(f"Download URL: {download_url}")

                                # Get sender info from sender object
                                sender = msg.get("sender", {})
                                sender_name = f"{sender.get('first_name', '')} {sender.get('last_name', '')}".strip() or "Unknown"

                                # Get file size in bytes
                                file_size = int(file_info.get("size_byte", 0))

                                # Extract encryption information
                                encrypted = file_info.get("encrypted", False)
                                e2e_iv = file_info.get("e2e_iv", "")

                                # Get file-specific encryption keys
                                file_key = ""
                                file_iv = ""
                                chat_key = ""
                                keys = file_info.get("keys", [])
                                if keys and len(keys) > 0:
                                    key_info = keys[0]  # Use first key (should be for this channel)
                                    file_key = key_info.get("key", "")
                                    file_iv = key_info.get("iv", "")
                                    chat_key = key_info.get("chat_key", "")

                                # Extract base64-encoded file data (embedded in response)
                                base_64_data = file_info.get("base_64", "")

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
                                    timestamp=str(msg.get("time", "")),
                                    encrypted=encrypted,
                                    e2e_iv=e2e_iv,
                                    file_key=file_key,
                                    file_iv=file_iv,
                                    chat_key=chat_key,
                                    base_64_data=base_64_data
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

    async def download_file(self, media_file: MediaFile, timeout: int = None) -> bytes:
        """Decrypt file data from base64-encoded embedded data

        Files are embedded in the message/content response as base64-encoded
        encrypted data. No separate download is needed.
        """
        try:
            logger.debug(f"Processing file ID: {media_file.file_id}")

            # File data is already embedded in the message response as base64
            if not media_file.base_64_data:
                raise ValueError(f"No base64 data found for file {media_file.file_id}")

            # Decode from hex string to bytes (it's hex-encoded, not base64!)
            encrypted_data = bytes.fromhex(media_file.base_64_data)
            logger.debug(f"Decoded {len(encrypted_data)} bytes from hex (encrypted)")

            # Decrypt if file is encrypted
            if media_file.encrypted and media_file.file_key and media_file.file_iv:
                try:
                    # Import crypto here to avoid circular imports
                    from ..crypto import HermineCrypto
                    from ..config import Config

                    # Get encryption password from config
                    config = Config()
                    crypto = HermineCrypto(
                        private_key_pem=self._get_private_key(),
                        encryption_password=config.hermine.encryption_key
                    )

                    # Decrypt the chat key first (it's RSA-encrypted and base64-encoded)
                    logger.debug(f"Decrypting chat_key (length: {len(media_file.chat_key)})")
                    decrypted_chat_key = crypto.decrypt_conversation_key(media_file.chat_key)
                    logger.debug(f"Chat key decrypted: {len(decrypted_chat_key)} bytes")

                    # The file_key might be hex-encoded AES key (possibly encrypted with chat_key)
                    # Try to use it directly first as hex
                    file_key_hex = media_file.file_key
                    file_iv_hex = media_file.file_iv

                    # If key is 96 hex chars (48 bytes), it might be key+IV or needs further decryption
                    if len(file_key_hex) == 96:
                        # Might be 32-byte key + 16-byte IV concatenated, or encrypted
                        logger.debug(f"File key is 48 bytes, might need decryption with chat_key")
                        # For now, try using first 64 chars (32 bytes) as key
                        file_key_bytes = bytes.fromhex(file_key_hex[:64])
                    elif len(file_key_hex) == 64:
                        # Standard 32-byte AES-256 key
                        file_key_bytes = bytes.fromhex(file_key_hex)
                    else:
                        logger.warning(f"Unexpected file_key length: {len(file_key_hex)} hex chars")
                        file_key_bytes = bytes.fromhex(file_key_hex)

                    file_iv_bytes = bytes.fromhex(file_iv_hex)
                    logger.debug(f"Using file key: {len(file_key_bytes)} bytes, IV: {len(file_iv_bytes)} bytes")

                    # Decrypt the file data
                    decrypted_data = crypto.decrypt_file(
                        encrypted_data,
                        file_key_bytes,
                        file_iv_bytes
                    )

                    logger.info(f"✓ Decrypted file: {len(encrypted_data)} → {len(decrypted_data)} bytes")
                    return decrypted_data

                except Exception as e:
                    logger.error(f"✗ Decryption failed: {e}")
                    logger.debug(f"File key length: {len(media_file.file_key)}, IV length: {len(media_file.file_iv)}")
                    logger.debug(f"Encrypted data length: {len(encrypted_data)}")
                    raise
            else:
                # File is not encrypted, return as-is
                logger.debug(f"File is not encrypted, returning {len(encrypted_data)} bytes")
                return encrypted_data

        except RequestException as e:
            logger.error(f"✗ Download fehlgeschlagen: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Decryption failed: {e}")
            raise

    @staticmethod
    def _is_media_file(mime_type: str) -> bool:
        """Check if MIME type is a media file"""
        media_prefixes = ('image/', 'video/', 'audio/')
        return any(mime_type.startswith(p) for p in media_prefixes)
