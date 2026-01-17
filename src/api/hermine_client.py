"""Hermine API Client"""
import logging
import asyncio
import random
import string
import json
from pathlib import Path
from datetime import datetime, timedelta
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

    # Session cache settings
    SESSION_CACHE_FILE = Path(".hermine_session.json")
    SESSION_CACHE_DAYS = 7

    def __init__(self, base_url: str, username: str, password: str,
                 timeout: int = 30, verify_ssl: bool = True):
        """Initialize Hermine client"""
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = requests.Session()

        # Try to load cached session
        cached_session = self._load_session_cache()

        if cached_session:
            # Use cached device_id and client_key
            self.device_id = cached_session["device_id"]
            self.client_key = cached_session["client_key"]
            self.user_id = cached_session.get("user_id")
            self.hidden_id = cached_session.get("hidden_id")
            logger.info(f"✓ Using cached session (device_id: {self.device_id[:8]}...)")
        else:
            # Generate new device ID
            self.device_id = "".join(random.choice(string.ascii_letters + string.digits)
                                    for _ in range(32))
            self.client_key = None
            self.user_id = None
            self.hidden_id = None
            logger.info(f"✓ Generated new device_id: {self.device_id[:8]}...")

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

        # Authenticate (will use cached session or create new one)
        if not cached_session:
            self._authenticate()
        else:
            # Verify cached session is still valid
            try:
                # Test with a simple API call
                self.get_companies()
                logger.info("✓ Cached session is still valid")
            except Exception as e:
                logger.warning(f"Cached session invalid: {e}, re-authenticating...")
                self.client_key = None
                self._authenticate()

    def _load_session_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached session from file if valid"""
        try:
            if not self.SESSION_CACHE_FILE.exists():
                return None

            with open(self.SESSION_CACHE_FILE, 'r') as f:
                cache = json.load(f)

            # Check expiration
            expires_at = datetime.fromisoformat(cache.get("expires_at", ""))
            if datetime.now() >= expires_at:
                logger.debug("Session cache expired")
                self.SESSION_CACHE_FILE.unlink(missing_ok=True)
                return None

            # Check username matches
            if cache.get("username") != self.username:
                logger.debug("Session cache username mismatch")
                return None

            logger.debug(f"Loaded session cache (expires: {expires_at.strftime('%Y-%m-%d %H:%M')})")
            return cache

        except Exception as e:
            logger.debug(f"Failed to load session cache: {e}")
            return None

    def _save_session_cache(self) -> None:
        """Save session to cache file"""
        try:
            cache = {
                "device_id": self.device_id,
                "client_key": self.client_key,
                "user_id": self.user_id,
                "hidden_id": self.hidden_id,
                "username": self.username,
                "expires_at": (datetime.now() + timedelta(days=self.SESSION_CACHE_DAYS)).isoformat()
            }

            with open(self.SESSION_CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2)

            logger.debug(f"Saved session cache (valid for {self.SESSION_CACHE_DAYS} days)")

        except Exception as e:
            logger.warning(f"Failed to save session cache: {e}")

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

            # Save session to cache
            self._save_session_cache()

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

            # Check if we have a 'keys' field (API returns this instead)
            if not private_key and "keys" in data:
                logger.debug("Found 'keys' field in response")
                keys = data.get("keys")
                logger.debug(f"Keys type: {type(keys)}, content: {keys if isinstance(keys, (dict, list)) else 'non-dict/list'}")

                # If keys is a dict, look for private_key inside
                if isinstance(keys, dict):
                    private_key = keys.get("private_key", "") or keys.get("privateKey", "") or keys.get("key", "")
                    logger.debug(f"Extracted key from dict, length: {len(private_key)}")
                # If keys is a list, take first item's private_key
                elif isinstance(keys, list) and len(keys) > 0:
                    logger.debug(f"Keys is a list with {len(keys)} items")
                    first_key = keys[0]
                    if isinstance(first_key, dict):
                        private_key = first_key.get("private_key", "") or first_key.get("privateKey", "") or first_key.get("key", "")
                        logger.debug(f"Extracted key from first list item, length: {len(private_key)}")

            # Check if key is still empty
            if not private_key or private_key.strip() == "":
                logger.error("Private key is empty after checking all fields!")
                logger.debug(f"Full response: {data}")
                raise ValueError("No private key found in API response. User may need to generate keys in the app first.")

            # Log key format for debugging
            key_length = len(private_key)
            key_start = private_key[:50] if len(private_key) > 50 else private_key
            logger.debug(f"Private key length: {key_length}, starts with: {key_start[:30]}...")

            # Check if key is JSON-wrapped (starts with "{")
            if private_key.strip().startswith("{"):
                logger.debug("Private key appears to be JSON-wrapped, parsing...")
                import json
                try:
                    key_json = json.loads(private_key)
                    # Extract the actual PEM key from the "private" field
                    if "private" in key_json:
                        private_key = key_json["private"]
                        logger.debug(f"Extracted PEM key from JSON, length: {len(private_key)}")
                    else:
                        logger.warning(f"JSON doesn't have 'private' field. Keys: {list(key_json.keys())}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse key as JSON: {e}, using as-is")

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

    def _download_full_file_from_endpoint(self, media_file: MediaFile, timeout: int = None) -> Optional[bytes]:
        """Attempt to download full file using /file/download endpoint with multipart form-data

        Args:
            media_file: MediaFile object with encryption info
            timeout: Optional timeout override

        Returns:
            Decrypted full file bytes, or None if download fails
        """
        try:
            # Use the browser's exact approach: POST to /file/download?id={file_id}
            # with multipart/form-data containing client_key and device_id
            download_url = f"{self.base_url}/file/download?id={media_file.file_id}"

            logger.debug(f"Attempting full file download from: {download_url}")

            # Prepare multipart form-data (like browser does)
            form_data = {
                'client_key': self.client_key,
                'device_id': self.device_id,
            }

            try:
                response = self.session.post(
                    download_url,
                    data=form_data,  # requests will automatically use multipart/form-data
                    timeout=timeout or self.timeout,
                    verify=self.verify_ssl,
                    headers={
                        "Origin": "https://app.thw-messenger.de",
                        "Referer": "https://app.thw-messenger.de/",
                    }
                )

                # Check response
                if response.status_code == 200:
                    encrypted_data = response.content
                    logger.debug(f"✓ Downloaded {len(encrypted_data)} bytes from /file/download endpoint")

                    # The response is encrypted, so decrypt it
                    if media_file.encrypted and media_file.file_key and media_file.file_iv:
                        from ..crypto import HermineCrypto
                        from ..config import Config
                        from Crypto.Cipher import AES
                        from Crypto.Util.Padding import unpad

                        config = Config()
                        crypto = HermineCrypto(
                            private_key_pem=self._get_private_key(),
                            encryption_password=config.hermine.encryption_key
                        )

                        # Decrypt chat key
                        decrypted_chat_key = crypto.decrypt_conversation_key(media_file.chat_key)

                        # Decrypt file key
                        encrypted_file_key = bytes.fromhex(media_file.file_key)
                        file_key_iv = bytes.fromhex(media_file.file_iv)
                        cipher = AES.new(decrypted_chat_key, AES.MODE_CBC, iv=file_key_iv)
                        padded_file_key = cipher.decrypt(encrypted_file_key)
                        file_key_bytes = unpad(padded_file_key, AES.block_size)

                        # Decrypt file data
                        file_data_iv = bytes.fromhex(media_file.e2e_iv)
                        decrypted_data = crypto.decrypt_file(
                            encrypted_data,
                            file_key_bytes,
                            file_data_iv
                        )

                        logger.info(f"✓ Downloaded and decrypted full file: {len(encrypted_data)} → {len(decrypted_data)} bytes")
                        return decrypted_data
                    else:
                        logger.debug("File not encrypted, returning as-is")
                        return encrypted_data
                else:
                    logger.debug(f"/file/download failed with status {response.status_code}: {response.text[:200]}")
                    return None

            except Exception as e:
                logger.debug(f"Failed to download from /file/download endpoint: {e}")
                return None

        except Exception as e:
            logger.debug(f"Full file download failed: {e}")
            return None

    async def download_file(self, media_file: MediaFile, timeout: int = None, prefer_full: bool = True) -> bytes:
        """Download and decrypt file data

        Args:
            media_file: MediaFile object with encryption info
            timeout: Optional timeout override
            prefer_full: If True, try to download full file from endpoint first, fallback to embedded thumbnail

        Returns:
            Decrypted file bytes
        """
        try:
            logger.debug(f"Processing file ID: {media_file.file_id}")

            # Try to download full file first if requested
            if prefer_full:
                full_file_data = self._download_full_file_from_endpoint(media_file, timeout)
                if full_file_data:
                    return full_file_data
                logger.debug("Full file download failed or not available, using embedded thumbnail data")

            # Fallback: Use embedded thumbnail data
            if not media_file.base_64_data:
                raise ValueError(f"No base64 data found for file {media_file.file_id}")

            # Decode from hex string to bytes (it's hex-encoded, not base64!)
            encrypted_data = bytes.fromhex(media_file.base_64_data)
            logger.debug(f"Decoded {len(encrypted_data)} bytes from hex (encrypted thumbnail)")

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

                    # The file_key is encrypted with the chat_key
                    # Decrypt it using AES with the file_iv
                    file_key_hex = media_file.file_key
                    file_iv_hex = media_file.file_iv

                    logger.debug(f"File key hex length: {len(file_key_hex)}, IV hex length: {len(file_iv_hex)}")

                    # Decrypt the file key using the chat key
                    encrypted_file_key = bytes.fromhex(file_key_hex)
                    file_key_iv = bytes.fromhex(file_iv_hex)

                    logger.debug(f"Decrypting file key ({len(encrypted_file_key)} bytes) with chat key...")

                    from Crypto.Cipher import AES
                    from Crypto.Util.Padding import unpad

                    # Decrypt the file key using AES-CBC with chat_key
                    cipher = AES.new(decrypted_chat_key, AES.MODE_CBC, iv=file_key_iv)
                    padded_file_key = cipher.decrypt(encrypted_file_key)
                    file_key_bytes = unpad(padded_file_key, AES.block_size)

                    logger.debug(f"Decrypted file key: {len(file_key_bytes)} bytes")

                    # Use e2e_iv for decrypting the actual file data
                    file_data_iv = bytes.fromhex(media_file.e2e_iv)
                    logger.debug(f"Using e2e_iv for file data decryption: {len(file_data_iv)} bytes")

                    # Decrypt the file data using the decrypted file key and e2e_iv
                    decrypted_data = crypto.decrypt_file(
                        encrypted_data,
                        file_key_bytes,
                        file_data_iv
                    )

                    logger.info(f"✓ Decrypted file (thumbnail): {len(encrypted_data)} → {len(decrypted_data)} bytes")
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

    def debug_dump_file_response(self, channel_id: str, limit: int = 1) -> Dict[str, Any]:
        """Debug method: Dump full API response for files in a channel

        Args:
            channel_id: Channel ID to fetch messages from
            limit: Number of messages to fetch (default: 1)

        Returns:
            Full API response dict with all fields
        """
        try:
            logger.info(f"=== DEBUG: Fetching message response for channel {channel_id} ===")

            data = self._post("message/content", {
                "channel_id": channel_id,
                "source": "channel",
                "limit": limit,
                "offset": 0,
            })

            # Pretty print the response
            logger.info("=== Full API Response ===")
            logger.info(json.dumps(data, indent=2, ensure_ascii=False))

            # Analyze file structure if present
            messages = data.get("messages", [])
            if messages:
                for idx, msg in enumerate(messages):
                    files = msg.get("files", [])
                    if files:
                        logger.info(f"\n=== Message {idx + 1} Files ===")
                        for file_idx, file_info in enumerate(files):
                            logger.info(f"\n--- File {file_idx + 1} ---")
                            logger.info(f"  ID: {file_info.get('id')}")
                            logger.info(f"  Name: {file_info.get('name')}")
                            logger.info(f"  Mime: {file_info.get('mime')}")
                            logger.info(f"  Size (bytes): {file_info.get('size_byte')}")
                            logger.info(f"  Encrypted: {file_info.get('encrypted')}")
                            logger.info(f"  E2E IV length: {len(file_info.get('e2e_iv', ''))}")

                            keys = file_info.get('keys', [])
                            if keys:
                                logger.info(f"  Keys count: {len(keys)}")
                                logger.info(f"  File key length: {len(keys[0].get('key', ''))}")
                                logger.info(f"  File IV length: {len(keys[0].get('iv', ''))}")
                                logger.info(f"  Chat key length: {len(keys[0].get('chat_key', ''))}")

                            base64_data = file_info.get('base_64', '')
                            logger.info(f"  Base64 data length: {len(base64_data)}")
                            if base64_data:
                                logger.info(f"  Base64 decoded size: {len(bytes.fromhex(base64_data))} bytes")

                            logger.info(f"  All fields: {list(file_info.keys())}")

            return data

        except Exception as e:
            logger.error(f"✗ Debug dump failed: {e}")
            raise

    def debug_test_file_download(self, file_id: str, file_name: str = "") -> Dict[str, Any]:
        """Debug method: Test /file/download endpoint with various approaches

        Args:
            file_id: File ID to download
            file_name: Optional filename

        Returns:
            Dict with test results
        """
        results = {
            "file_id": file_id,
            "file_name": file_name,
            "tests": []
        }

        logger.info(f"\n=== DEBUG: Testing /file/download endpoint for file {file_id} ===")

        # Test 1: POST with file_id
        logger.info("\n--- Test 1: POST with file_id parameter ---")
        try:
            data = self._post("file/download", {"file_id": file_id})
            logger.info(f"✓ Test 1 succeeded!")
            logger.info(f"Response keys: {list(data.keys())}")
            logger.info(f"Response: {json.dumps(data, indent=2)[:500]}...")
            results["tests"].append({
                "name": "POST with file_id",
                "success": True,
                "response": data
            })
        except Exception as e:
            logger.warning(f"✗ Test 1 failed: {e}")
            results["tests"].append({
                "name": "POST with file_id",
                "success": False,
                "error": str(e)
            })

        # Test 2: POST with id parameter
        logger.info("\n--- Test 2: POST with id parameter ---")
        try:
            data = self._post("file/download", {"id": file_id})
            logger.info(f"✓ Test 2 succeeded!")
            logger.info(f"Response: {json.dumps(data, indent=2)[:500]}...")
            results["tests"].append({
                "name": "POST with id",
                "success": True,
                "response": data
            })
        except Exception as e:
            logger.warning(f"✗ Test 2 failed: {e}")
            results["tests"].append({
                "name": "POST with id",
                "success": False,
                "error": str(e)
            })

        # Test 3: Direct URL download
        if file_name:
            logger.info("\n--- Test 3: Direct URL download ---")
            try:
                url = f"https://app.thw-messenger.de/thw/app.thw-messenger.de/{file_id}/{file_name}"
                response = self.session.get(url, timeout=self.timeout, verify=self.verify_ssl)
                logger.info(f"Status: {response.status_code}")
                logger.info(f"Headers: {dict(response.headers)}")
                logger.info(f"Content length: {len(response.content)} bytes")

                if response.status_code == 200:
                    logger.info(f"✓ Test 3 succeeded!")
                    results["tests"].append({
                        "name": "Direct URL download",
                        "success": True,
                        "status_code": response.status_code,
                        "content_length": len(response.content)
                    })
                else:
                    logger.warning(f"✗ Test 3 failed with status {response.status_code}")
                    results["tests"].append({
                        "name": "Direct URL download",
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text[:200]
                    })
            except Exception as e:
                logger.warning(f"✗ Test 3 failed: {e}")
                results["tests"].append({
                    "name": "Direct URL download",
                    "success": False,
                    "error": str(e)
                })

        # Test 4: Try file/get endpoint
        logger.info("\n--- Test 4: POST to file/get endpoint ---")
        try:
            data = self._post("file/get", {"file_id": file_id})
            logger.info(f"✓ Test 4 succeeded!")
            logger.info(f"Response: {json.dumps(data, indent=2)[:500]}...")
            results["tests"].append({
                "name": "POST to file/get",
                "success": True,
                "response": data
            })
        except Exception as e:
            logger.warning(f"✗ Test 4 failed: {e}")
            results["tests"].append({
                "name": "POST to file/get",
                "success": False,
                "error": str(e)
            })

        # Test 5: POST with multipart/form-data (browser method)
        logger.info("\n--- Test 5: POST with multipart/form-data (browser method) ---")
        try:
            download_url = f"{self.base_url}/file/download?id={file_id}"
            form_data = {
                'client_key': self.client_key,
                'device_id': self.device_id,
            }
            response = self.session.post(
                download_url,
                data=form_data,
                timeout=self.timeout,
                verify=self.verify_ssl,
                headers={
                    "Origin": "https://app.thw-messenger.de",
                    "Referer": "https://app.thw-messenger.de/",
                }
            )
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Content length: {len(response.content)} bytes")
            logger.info(f"Content type: {response.headers.get('Content-Type')}")

            if response.status_code == 200:
                logger.info(f"✓ Test 5 succeeded!")
                results["tests"].append({
                    "name": "POST with multipart/form-data",
                    "success": True,
                    "status_code": response.status_code,
                    "content_length": len(response.content)
                })
            else:
                logger.warning(f"✗ Test 5 failed with status {response.status_code}")
                results["tests"].append({
                    "name": "POST with multipart/form-data",
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text[:200]
                })
        except Exception as e:
            logger.warning(f"✗ Test 5 failed: {e}")
            results["tests"].append({
                "name": "POST with multipart/form-data",
                "success": False,
                "error": str(e)
            })

        # Summary
        logger.info("\n=== Test Summary ===")
        success_count = sum(1 for t in results["tests"] if t["success"])
        logger.info(f"Passed: {success_count}/{len(results['tests'])}")

        return results

    @staticmethod
    def _is_media_file(mime_type: str) -> bool:
        """Check if MIME type is a media file"""
        media_prefixes = ('image/', 'video/', 'audio/')
        return any(mime_type.startswith(p) for p in media_prefixes)
