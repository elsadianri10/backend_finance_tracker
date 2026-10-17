import json
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from uuid import UUID

from PIL import Image
from fastapi import HTTPException
from sqlalchemy import select
import test_billing as fixture
import test_wishlists as wishlist_fixture
from app.models.wishlist_model import WishlistPhoto
from app.services import wishlist_image_service as images


def image_bytes():
    output = BytesIO()
    Image.new('RGB', (40, 30), 'red').save(output, 'PNG')
    return output.getvalue()


class WishlistUploadTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers
    create = wishlist_fixture.WishlistTests.create
    item = wishlist_fixture.WishlistTests.item
    share = wishlist_fixture.WishlistTests.share

    async def upload(self, row, *, item=None, files=None, photos=None, headers=None, name='Uploaded'):
        return await self.client.request('PATCH' if item else 'POST', '/wishlists/' + row['Id'] + '/items' + ('/' + item['Id'] if item else '') + '/upload',
            headers=headers or self.headers, data={'metadata': json.dumps({'Name': name, 'GroupId': row['Groups'][0]['Id'], 'Photos': photos or []})},
            files=files if files is not None else [('files', ('photo.png', image_bytes(), 'image/png'))])

    async def test_upload_private_shared_revoke_and_cleanup(self):
        row = await self.create()
        blobs = ['https://test.private.blob.vercel-storage.com/wishlist/a.webp', 'https://test.private.blob.vercel-storage.com/wishlist/b.webp']
        with patch.object(images, 'put', new=AsyncMock(side_effect=blobs)) as put, patch.object(images, 'read', new=AsyncMock(return_value=b'private-image')) as read, patch.object(images, 'cleanup', new=AsyncMock()) as cleanup:
            response = await self.upload(row, files=[('files', ('a.png', image_bytes(), 'image/png')), ('files', ('b.png', image_bytes(), 'image/png'))])
            self.assertEqual(response.status_code, 201, response.text)
            item = response.json()['Groups'][0]['Items'][0]
            self.assertEqual(len(item['Photos']), 2)
            self.assertNotIn('blob.vercel', response.text)
            self.assertTrue(put.call_args.args[1].startswith(b'RIFF'))
            path = item['Photos'][0].removeprefix('/api')
            self.assertEqual((await self.client.get(path)).status_code, 404)
            self.assertEqual((await self.client.get(path, headers=self.auth_headers(self.other_id))).status_code, 404)
            image = await self.client.get(path, headers=self.headers)
            self.assertEqual(image.content, b'private-image')
            self.assertIn('no-store', image.headers['cache-control'])
            self.assertEqual(image.headers['content-type'], 'image/webp')
            public = await self.share(row)
            token = public.rsplit('/', 1)[1]
            public_item = (await self.client.get(public)).json()['Groups'][0]['Items'][0]
            self.assertEqual(public_item['Photos'][0], item['Photos'][0] + '&share=' + token)
            self.assertEqual((await self.client.get(path + '&share=' + token)).status_code, 200)
            before = read.await_count
            await self.client.delete('/wishlists/' + row['Id'] + '/share', headers=self.headers)
            self.assertEqual((await self.client.get(path + '&share=' + token)).status_code, 404)
            self.assertEqual(read.await_count, before)
            # Reordering retains the correct object, then deleting cleans it up.
            edited = await self.client.patch('/wishlists/' + row['Id'] + '/items/' + item['Id'], headers=self.headers,
                json={'GroupId': row['Groups'][0]['Id'], 'Name': 'Edited', 'Photos': [item['Photos'][1], 'https://example.test/external.jpg']})
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertNotEqual(edited.json()['Groups'][0]['Items'][0]['Photos'][0], item['Photos'][0])
            cleanup.assert_awaited_with([blobs[0]])
            async with self.sessions() as db:
                photo = await db.scalar(select(WishlistPhoto).where(WishlistPhoto.item_id == UUID(item['Id']), WishlistPhoto.position == 0))
                self.assertEqual(photo.blob_url, blobs[1])
            await self.client.delete('/wishlists/' + row['Id'] + '/items/' + item['Id'], headers=self.headers)
            cleanup.assert_awaited_with([blobs[1]])

    async def test_validation_ownership_and_failed_upload_are_atomic(self):
        row = await self.create()
        item = await self.item(row, Photos=['https://example.test/original.jpg'])
        with patch.object(images, 'put', new=AsyncMock()) as put:
            self.assertEqual((await self.upload(row, headers=self.auth_headers(self.other_id))).status_code, 404)
            self.assertEqual((await self.upload(row, files=[('files', ('bad.png', b'not-an-image', 'image/png'))])).status_code, 422)
            self.assertEqual((await self.upload(row, files=[('files', ('big.png', b'x' * 450001, 'image/png'))])).status_code, 413)
            self.assertEqual((await self.upload(row, photos=['https://example.test/a'] * 6)).status_code, 422)
            self.assertEqual((await self.upload(row, photos=['/api/wishlists/images/' + item['Id'] + '/0'])).status_code, 422)
            put.assert_not_awaited()
        blob = 'https://test.private.blob.vercel-storage.com/wishlist/new.webp'
        with patch.object(images, 'put', new=AsyncMock(side_effect=[blob, HTTPException(503, 'storage')])), patch.object(images, 'cleanup', new=AsyncMock()) as cleanup:
            response = await self.upload(row, item=item, name='Should rollback', files=[('files', ('a.png', image_bytes())), ('files', ('b.png', image_bytes()))])
            self.assertEqual(response.status_code, 503)
            cleanup.assert_awaited_with([blob])
        current = (await self.client.get('/wishlists', headers=self.headers)).json()[0]['Groups'][0]['Items']
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['Name'], 'Item')
        self.assertEqual(current[0]['Photos'], ['https://example.test/original.jpg'])

    async def test_archived_photos_and_cross_item_references(self):
        row = await self.create()
        with patch.object(images, 'put', new=AsyncMock(return_value='https://test.private.blob.vercel-storage.com/wishlist/a.webp')), patch.object(images, 'cleanup', new=AsyncMock()), patch.object(images, 'read', new=AsyncMock(return_value=b'image')) as read:
            item = (await self.upload(row)).json()['Groups'][0]['Items'][0]
            second = await self.item(row, Name='Z Second')
            response = await self.client.patch('/wishlists/' + row['Id'] + '/items/' + second['Id'], headers=self.headers,
                json={'Name': 'Second', 'GroupId': row['Groups'][0]['Id'], 'Photos': item['Photos']})
            self.assertEqual(response.status_code, 422)
            public = await self.share(row)
            await self.client.patch('/wishlists/' + row['Id'] + '/items/' + item['Id'], headers=self.headers,
                json={'Name': 'Archived', 'GroupId': row['Groups'][0]['Id'], 'Photos': item['Photos'], 'Status': 'archived'})
            self.assertEqual((await self.client.get(item['Photos'][0].removeprefix('/api') + '&share=' + public.rsplit('/', 1)[1])).status_code, 404)
            read.assert_not_awaited()
