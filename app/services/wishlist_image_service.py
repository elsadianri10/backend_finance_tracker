"""Private Blob storage; credentials and upstream URLs never reach the browser."""
import logging
import os
import re
import warnings
from io import BytesIO
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import HTTPException
from PIL import Image, ImageOps

MAX_IMAGE_BYTES = 450_000
API = 'https://vercel.com/api/blob'
logger = logging.getLogger(__name__)


def credentials():
    token = os.environ.get('BLOB_READ_WRITE_TOKEN', '').strip()
    parts = token.split('_')
    if len(parts) < 5 or not re.fullmatch(r'[A-Za-z0-9]+', parts[3]):
        raise HTTPException(503, 'Penyimpanan foto belum dikonfigurasi')
    return token, parts[3]


def headers():
    token, store = credentials()
    return {'Authorization': f'Bearer {token}', 'x-api-version': '13', 'x-vercel-blob-store-id': store}


def private_url(url: str):
    _, store = credentials()
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc != f'{store.lower()}.private.blob.vercel-storage.com'
            or not parsed.path.startswith('/wishlist/') or parsed.query or parsed.fragment):
        raise HTTPException(503, 'Alamat penyimpanan foto tidak valid')
    return url


def normalize(data: bytes) -> bytes:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, 'Foto terlalu besar. Pilih ulang foto melalui form upload.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or getattr(image, 'is_animated', False):
                    raise ValueError('format')
                if image.width * image.height > 20_000_000:
                    raise ValueError('pixels')
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((1600, 1600))
                output = BytesIO()
                image.save(output, format='WEBP', quality=80)
                result = output.getvalue()
                if len(result) > MAX_IMAGE_BYTES:
                    raise HTTPException(413, 'Foto terlalu besar. Pilih foto dengan resolusi lebih kecil.')
                return result
    except HTTPException:
        raise
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(422, 'Foto harus berupa gambar JPG, PNG, atau WebP yang valid') from None


async def put(item_id, data: bytes) -> str:
    path = f'wishlist/{item_id}/{uuid4()}.webp'
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.put(API, params={'pathname': path}, content=data, headers={
                **headers(), 'x-vercel-blob-access': 'private', 'x-content-type': 'image/webp',
                'Content-Type': 'image/webp', 'x-add-random-suffix': '0', 'x-allow-overwrite': '0',
            })
            response.raise_for_status()
            return private_url(response.json()['url'])
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Upload foto belum berhasil. Silakan coba lagi.') from None


async def read(url: str) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream('GET', private_url(url), headers=headers()) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_IMAGE_BYTES:
                        raise HTTPException(503, 'Foto tidak dapat dimuat')
                return bytes(data)
    except httpx.HTTPError:
        raise HTTPException(503, 'Foto belum dapat dimuat. Silakan coba lagi.') from None


async def cleanup(urls):
    """Best effort after commit: storage failures must not undo a saved edit."""
    if not urls:
        return
    try:
        validated = [private_url(url) for url in set(urls)]
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(API + '/delete', headers=headers(), json={'urls': validated})
            response.raise_for_status()
    except (httpx.HTTPError, HTTPException):
        logger.warning('Wishlist Blob cleanup failed; unused objects need storage cleanup')
