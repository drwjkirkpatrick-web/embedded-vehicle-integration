"""
Tests for embedded_vehicle.security.encryption — CryptoVault.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from embedded_vehicle.security.encryption import CryptoVault


def test_vault_encrypt_decrypt(tmp_path: Path) -> None:
    key_path = tmp_path / "test.key"
    vault = CryptoVault(key_path=key_path)
    plaintext = b"secret telemetry data"
    ciphertext = vault.encrypt(plaintext)
    assert ciphertext != plaintext
    decrypted = vault.decrypt(ciphertext)
    assert decrypted == plaintext


def test_vault_key_persisted(tmp_path: Path) -> None:
    key_path = tmp_path / "test.key"
    vault1 = CryptoVault(key_path=key_path)
    vault2 = CryptoVault(key_path=key_path)
    # Same key should produce compatible encryption/decryption
    ct = vault1.encrypt(b"hello")
    assert vault2.decrypt(ct) == b"hello"


def test_vault_file_encrypt_decrypt(tmp_path: Path) -> None:
    key_path = tmp_path / "test.key"
    vault = CryptoVault(key_path=key_path)
    src = tmp_path / "plain.txt"
    src.write_bytes(b"file contents")
    enc = vault.encrypt_file(src, remove_plain=True)
    assert enc.exists()
    assert not src.exists()
    dec = vault.decrypt_file(enc, tmp_path / "out.txt")
    assert dec.read_bytes() == b"file contents"


def test_vault_bad_decrypt_raises(tmp_path: Path) -> None:
    from cryptography.fernet import InvalidToken
    key_path = tmp_path / "test.key"
    vault = CryptoVault(key_path=key_path)
    with pytest.raises(InvalidToken):
        vault.decrypt(b"not valid ciphertext")
