"""Hermine end-to-end decryption module.

Handles RSA private key decryption and AES file/message decryption.
"""

import base64
import json
import logging
from typing import Optional, Tuple

from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import unpad

logger = logging.getLogger(__name__)


class HermineCrypto:
    """Hermine E2E Cryptography Handler"""

    def __init__(self, private_key_pem: str, encryption_password: str):
        """Initialize crypto with private key.

        Args:
            private_key_pem: PEM-encoded RSA private key
            encryption_password: Passphrase for private key
        """
        try:
            passphrase = encryption_password.encode() if isinstance(encryption_password, str) else encryption_password

            # Try to import the key with passphrase first
            try:
                self.private_key = RSA.import_key(private_key_pem, passphrase=passphrase)
                logger.info("✓ Private key loaded successfully (with passphrase)")
            except (ValueError, IndexError, TypeError) as e:
                logger.debug(f"Failed with passphrase: {e}, trying without passphrase")
                # Try without passphrase
                try:
                    self.private_key = RSA.import_key(private_key_pem)
                    logger.info("✓ Private key loaded successfully (without passphrase)")
                except Exception as e2:
                    logger.error(f"Failed to load key without passphrase: {e2}")
                    # Try alternative PEM headers
                    if "-----BEGIN RSA PRIVATE KEY-----" in private_key_pem:
                        alt_key = private_key_pem.replace("-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----")
                        alt_key = alt_key.replace("-----END RSA PRIVATE KEY-----", "-----END PRIVATE KEY-----")
                        logger.debug("Trying with alternative PEM headers (PRIVATE KEY)")
                        self.private_key = RSA.import_key(alt_key, passphrase=passphrase)
                        logger.info("✓ Private key loaded successfully (alternative format)")
                    else:
                        raise
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            logger.debug(f"Key starts with: {private_key_pem[:100]}...")
            raise

    def decrypt_conversation_key(
        self,
        encrypted_key: str
    ) -> bytes:
        """Decrypt conversation/channel key using RSA.
        
        Args:
            encrypted_key: Base64-encoded encrypted AES key
            
        Returns:
            Decrypted AES key (32 bytes)
        """
        try:
            decryptor = PKCS1_OAEP.new(self.private_key)
            encrypted_bytes = base64.b64decode(encrypted_key)
            decrypted_key = decryptor.decrypt(encrypted_bytes)
            logger.debug(f"Decrypted conversation key: {len(decrypted_key)} bytes")
            return decrypted_key
        except Exception as e:
            logger.error(f"Failed to decrypt conversation key: {e}")
            raise

    def decrypt_file(
        self,
        encrypted_data: bytes,
        file_key: bytes,
        iv: bytes
    ) -> bytes:
        """Decrypt file data using AES-CBC.
        
        Args:
            encrypted_data: Encrypted file content
            file_key: AES key (32 bytes)
            iv: Initialization vector (16 bytes)
            
        Returns:
            Decrypted file content
        """
        try:
            cipher = AES.new(file_key, AES.MODE_CBC, iv=iv)
            padded_data = cipher.decrypt(encrypted_data)
            decrypted_data = unpad(padded_data, AES.block_size)
            logger.debug(f"Decrypted file: {len(decrypted_data)} bytes")
            return decrypted_data
        except Exception as e:
            logger.error(f"Failed to decrypt file: {e}")
            raise

    def decrypt_message_text(
        self,
        encrypted_text: str,
        conversation_key: bytes,
        iv: str
    ) -> str:
        """Decrypt message text using AES-CBC.
        
        Args:
            encrypted_text: Hex-encoded encrypted text
            conversation_key: AES key from conversation
            iv: Hex-encoded initialization vector
            
        Returns:
            Decrypted message text
        """
        try:
            encrypted_bytes = bytes.fromhex(encrypted_text)
            iv_bytes = bytes.fromhex(iv)
            cipher = AES.new(conversation_key, AES.MODE_CBC, iv=iv_bytes)
            padded_text = cipher.decrypt(encrypted_bytes)
            decrypted_text = unpad(padded_text, AES.block_size)
            return decrypted_text.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt message text: {e}")
            raise

    def decrypt_location(
        self,
        encrypted_lat: str,
        encrypted_lon: str,
        conversation_key: bytes,
        iv: str
    ) -> Tuple[float, float]:
        """Decrypt location coordinates.
        
        Args:
            encrypted_lat: Hex-encoded encrypted latitude
            encrypted_lon: Hex-encoded encrypted longitude
            conversation_key: AES key from conversation
            iv: Hex-encoded initialization vector
            
        Returns:
            Tuple of (latitude, longitude)
        """
        try:
            lat_str = self.decrypt_message_text(encrypted_lat, conversation_key, iv)
            lon_str = self.decrypt_message_text(encrypted_lon, conversation_key, iv)
            return float(lat_str), float(lon_str)
        except Exception as e:
            logger.error(f"Failed to decrypt location: {e}")
            raise
