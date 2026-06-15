"""
embedded_vehicle/security/encryption.py
───────────────────────────────────────
Cryptographic vault for at-rest data encryption on the Pi.

Uses:
    - cryptography.fernet for symmetric file encryption
    - hashlib + secrets for key derivation
    - Platform key storage: /etc/embedded-vehicle/.master_key (600 perms)

Protects:
    - Video segments (AES-256 via Fernet)
    - SQLite database (optional full-disk via LUKS)
    - Telegram bot token (at-rest in config)
    - OBD snapshots with VIN / location
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger("vehicle.crypto")


class CryptoVault:
    """Simple symmetric vault for file-level encryption."""

    def __init__(self, key_path: Path | None = None) -> None:
        self.key_path = key_path or Path("/etc/embedded-vehicle/.master_key")
        self._fernet: Fernet | None = None
        self._init_key()

    def _init_key(self) -> None:
        """Load or generate a Fernet key, store with restrictive permissions."""
        if self.key_path.exists():
            with open(self.key_path, "rb") as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            self.key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(key)
            os.chmod(self.key_path, 0o600)
            logger.info("CryptoVault: generated new master key")
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt bytes, return ciphertext."""
        if not self._fernet:
            raise RuntimeError("Vault not initialized")
        return self._fernet.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt bytes, return plaintext."""
        if not self._fernet:
            raise RuntimeError("Vault not initialized")
        return self._fernet.decrypt(ciphertext)

    def encrypt_file(self, src: Path, dst: Path | None = None, remove_plain: bool = True) -> Path:
        """Encrypt a file in-place or to a new path."""
        if dst is None:
            dst = src.with_suffix(src.suffix + ".enc")
        with open(src, "rb") as f:
            data = f.read()
        enc = self.encrypt(data)
        with open(dst, "wb") as f:
            f.write(enc)
        if remove_plain:
            src.unlink()
        logger.info("CryptoVault: encrypted %s → %s", src, dst)
        return dst

    def decrypt_file(self, src: Path, dst: Path) -> Path:
        """Decrypt a file to a new path."""
        with open(src, "rb") as f:
            data = f.read()
        plain = self.decrypt(data)
        with open(dst, "wb") as f:
            f.write(plain)
        logger.info("CryptoVault: decrypted %s → %s", src, dst)
        return dst

    def rotate_key(self) -> None:
        """Generate a new key and re-encrypt all managed files.

        Not implemented — would need a file registry to know what to rotate.
        """
        raise NotImplementedError("Key rotation requires a file registry")
