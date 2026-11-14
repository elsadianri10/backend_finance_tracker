"""Small HTTP adapter. Never include provider errors or credentials in API responses."""
import os
import re
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException


def configuration():
    mode = os.getenv('MIDTRANS_ENVIRONMENT', 'sandbox').strip()
    if mode not in {'sandbox', 'production'}:
        raise HTTPException(503, 'Konfigurasi pembayaran tidak valid')
    key = os.getenv('MIDTRANS_SERVER_KEY', '').strip()
    origin = os.getenv('SUBSCRIPTION_FRONTEND_URL', '').strip().rstrip('/')
    parsed = urlparse(origin)
    valid_origin = parsed.scheme == 'https' or (mode == 'sandbox' and parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'})
    enabled = os.getenv('MIDTRANS_ENABLED', 'false').lower() == 'true'
    if enabled and mode == 'sandbox' and os.getenv('VERCEL_ENV') == 'production':
        raise HTTPException(503, 'Sandbox hanya untuk lingkungan pengujian')
    if enabled and (not key or not os.getenv('MIDTRANS_WEBHOOK_TOKEN') or not valid_origin or parsed.path not in {'', '/'} or parsed.query or parsed.fragment or parsed.username):
        raise HTTPException(503, 'Konfigurasi pembayaran belum lengkap')
    return mode, key, origin, enabled


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.~-]{1,100}', value):
        raise HTTPException(422, 'Identitas pembayaran tidak valid')
    return value


async def call(method, path, payload=None, *, snap=False, idempotency=None):
    mode, key, _, enabled = configuration()
    if not enabled:
        raise HTTPException(503, 'Pembayaran belum tersedia')
    domain = ('app.' if snap else 'api.') + ('sandbox.' if mode == 'sandbox' else '') + 'midtrans.com'
    headers = {'Accept': 'application/json'}
    if idempotency:
        headers['Idempotency-Key'] = idempotency
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.request(method, 'https://' + domain + path, json=payload,
                auth=(key, ''), headers=headers)
        if response.status_code == 404:
            raise HTTPException(404, 'Pembayaran belum ditemukan di Midtrans')
        if response.status_code >= 400:
            raise HTTPException(502, 'Midtrans belum dapat memproses permintaan')
        data = response.json()
        if not isinstance(data, dict) or int(data.get('status_code', 200)) >= 400:
            raise HTTPException(502, 'Midtrans belum dapat memproses permintaan')
        return data
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise HTTPException(502, 'Koneksi pembayaran belum berhasil. Periksa status sebelum mencoba lagi.') from exc


def checkout_url(value):
    mode, _, _, _ = configuration()
    expected = 'app.sandbox.midtrans.com' if mode == 'sandbox' else 'app.midtrans.com'
    parsed = urlparse(value or '')
    if parsed.scheme != 'https' or parsed.netloc != expected or not parsed.path.startswith('/snap/'):
        raise HTTPException(502, 'Tautan pembayaran tidak valid')
    return value
