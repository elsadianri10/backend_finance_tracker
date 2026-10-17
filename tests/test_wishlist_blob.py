import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException
from app.services import wishlist_image_service as images


class BlobAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_protocol_and_redirect_rejection(self):
        requests = []
        url = 'https://store.private.blob.vercel-storage.com/wishlist/synthetic.webp'
        def handle(request):
            requests.append(request)
            self.assertEqual(request.headers['authorization'], 'Bearer vercel_blob_rw_store_test')
            if request.method == 'PUT':
                self.assertEqual(str(request.url).split('?')[0], images.API)
                self.assertTrue(request.url.params['pathname'].startswith('wishlist/'))
                self.assertEqual(request.headers['x-vercel-blob-access'], 'private')
                self.assertEqual(request.headers['x-add-random-suffix'], '0')
                self.assertEqual(request.headers['x-api-version'], '13')
                return httpx.Response(200, json={'url': url})
            if request.method == 'POST':
                self.assertEqual(str(request.url), images.API + '/delete')
                self.assertEqual(request.read(), b'{"urls":["' + url.encode() + b'"]}')
                return httpx.Response(200, json={})
            return httpx.Response(200, content=b'webp')
        original = httpx.AsyncClient
        def client(**options):
            self.assertFalse(options['follow_redirects'])
            return original(**options, transport=httpx.MockTransport(handle))
        with patch.dict(os.environ, {'BLOB_READ_WRITE_TOKEN': 'vercel_blob_rw_store_test'}), patch.object(images.httpx, 'AsyncClient', side_effect=client):
            self.assertEqual(await images.put(uuid4(), b'webp'), url)
            self.assertEqual(await images.read(url), b'webp')
            await images.cleanup([url])
            self.assertEqual(len(requests), 3)
            for invalid in ('https://evil.example/wishlist/a', 'https://store.public.blob.vercel-storage.com/wishlist/a', url + '?redirect=1', 'http://' + url[8:]):
                with self.assertRaises(HTTPException):
                    await images.read(invalid)
            self.assertEqual(len(requests), 3)

    async def test_missing_credentials_and_provider_errors_are_sanitized(self):
        with patch.dict(os.environ, {'BLOB_READ_WRITE_TOKEN': ''}):
            with self.assertRaises(HTTPException) as error:
                images.credentials()
            self.assertEqual(error.exception.status_code, 503)
        original = httpx.AsyncClient
        def client(**options):
            return original(**options, transport=httpx.MockTransport(lambda _: httpx.Response(403, text='secret-provider-error')))
        with patch.dict(os.environ, {'BLOB_READ_WRITE_TOKEN': 'vercel_blob_rw_store_test'}), patch.object(images.httpx, 'AsyncClient', side_effect=client):
            with self.assertRaises(HTTPException) as error:
                await images.put(uuid4(), b'image')
            self.assertEqual(error.exception.status_code, 503)
            self.assertNotIn('secret-provider-error', error.exception.detail)
