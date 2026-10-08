import base64
import os
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException


def encryption_key() -> bytes:
    try:
        key = bytes.fromhex(os.getenv("ENCRYPTION_KEY", ""))
    except ValueError:
        key = b""
    if len(key) != 32:
        raise HTTPException(503, "Configure ENCRYPTION_KEY as a 32-byte hex key")
    return key


def encrypt_account_number(number: str, account_id: UUID, user_id: UUID) -> str:
    nonce = os.urandom(12)
    aad = f"billing-account:{user_id}:{account_id}".encode()
    ciphertext = AESGCM(encryption_key()).encrypt(nonce, number.encode(), aad)
    return base64.b64encode(nonce + ciphertext).decode()


def masked_account_number(encrypted: str, account_id: UUID, user_id: UUID) -> str:
    key = encryption_key()
    try:
        raw = base64.b64decode(encrypted, validate=True)
        aad = f"billing-account:{user_id}:{account_id}".encode()
        number = AESGCM(key).decrypt(raw[:12], raw[12:], aad).decode()
    except (ValueError, InvalidTag, UnicodeError) as exc:
        raise HTTPException(503, "Account number could not be read; check encryption configuration") from exc
    return "*" * (len(number) - 4) + number[-4:]
