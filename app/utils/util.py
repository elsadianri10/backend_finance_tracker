import asyncio
import bcrypt
import os
from base64 import b64encode, b64decode
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from sqlalchemy.exc import OperationalError
from typing import TypeVar, Callable, Awaitable
from cryptography.exceptions import InvalidTag
from app.utils import logger
from app.config import APP_TZ

async def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

_R = TypeVar("_R")
async def retry_query_on_error(query_func: Callable[[], Awaitable[_R]], retries: int = 3, delay: int = 2) -> _R:
    for attempt in range(retries):
        try:
            return await query_func()
        except OperationalError as e:
            logger.warning("Operational error on attempt '%s': %s", attempt + 1, e, exc_info=True)
            if attempt < retries - 1:
                delay_seconds = delay * (2 ** attempt)
                await asyncio.sleep(delay_seconds)
            else:
                raise
        except Exception as e:
            logger.error("Unexpected error during query execution: %s", e, exc_info=True)
            raise
    # This line should be unreachable, but satisfies the type checker:
    raise RuntimeError("retry_query_on_error: reached unreachable code")

def _get_enc_key_bytes() -> bytes:
    encrypt_key = os.getenv("ENCRYPTION_KEY")
    if encrypt_key is None:
        raise ValueError("ENCRYPTION_KEY environment variable is not set")

    try:
        key = bytes.fromhex(encrypt_key)
    except ValueError:
        raise ValueError("ENCRYPTION_KEY must be a valid hex string")

    if len(key) not in (16, 24, 32):
        raise ValueError("ENCRYPTION_KEY must decode to 16/24/32 bytes (AES-128/192/256)")

    return key

async def encrypt(plaintext: str) -> str:
    encryption_key = _get_enc_key_bytes()
    iv = os.urandom(12)  # GCM nonce 12 bytes

    encryptor = Cipher(
        algorithms.AES(encryption_key),
        modes.GCM(iv),
        backend=default_backend()
    ).encryptor()

    ciphertext = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()

    # layout: iv(12) + tag(16) + ciphertext
    encrypted_data = iv + encryptor.tag + ciphertext
    return b64encode(encrypted_data).decode("utf-8")

async def decrypt(encrypted_data: str) -> str:
    raw = b64decode(encrypted_data)
    key = _get_enc_key_bytes()

    candidates = []

    if len(raw) >= 12 + 16:
        iv = raw[:12]
        tag = raw[12:12+16]
        ct  = raw[12+16:]
        candidates.append((iv, tag, ct))

        iv = raw[:12]
        tag = raw[-16:]
        ct  = raw[12:-16]
        candidates.append((iv, tag, ct))

    if len(raw) >= 16 + 16:
        iv = raw[:16]
        tag = raw[-16:]
        ct  = raw[16:-16]
        candidates.append((iv, tag, ct))

    last_err: Exception | None = None
    for iv, tag, ciphertext in candidates:
        try:
            decryptor = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend()
            ).decryptor()

            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext.decode("utf-8")
        except InvalidTag as e:
            last_err = e
            continue

    raise ValueError("Invalid encrypted_data (GCM tag mismatch / wrong layout or key)") from last_err

def hash_password(plain_password: str) -> str:
    if plain_password is None:
        raise ValueError("plain_password is required")
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

# Datetime
def app_now():
    return datetime.now(APP_TZ).replace(tzinfo=None)