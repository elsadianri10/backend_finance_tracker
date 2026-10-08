import base64
import os
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from app.helpers.billing_encryption import encryption_key


def encrypt(number, account_id, user_id, field):
    nonce = os.urandom(12)
    aad = f"bank-account:{user_id}:{account_id}:{field}".encode()
    encrypted = AESGCM(encryption_key()).encrypt(nonce, number.encode(), aad)
    return base64.b64encode(nonce + encrypted).decode()


def masked(encrypted, account_id, user_id, field):
    try:
        raw = base64.b64decode(encrypted, validate=True)
        aad = f"bank-account:{user_id}:{account_id}:{field}".encode()
        number = AESGCM(encryption_key()).decrypt(raw[:12], raw[12:], aad).decode()
    except (ValueError, InvalidTag, UnicodeError) as exc:
        raise HTTPException(503, "Bank account number could not be read") from exc
    return "*" * (len(number) - 4) + number[-4:]
