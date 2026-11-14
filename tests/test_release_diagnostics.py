import unittest,logging
from unittest.mock import patch
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from app.helpers.request_diagnostics import RequestDiagnostics
class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_reference_does_not_log_payload_url_or_exception_message(self):
        app=FastAPI();app.add_middleware(RequestDiagnostics)
        @app.get('/synthetic/{secret}')
        async def fail(secret:str):raise RuntimeError('password=never-log-this')
        async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            with self.assertLogs('finance.requests',level=logging.WARNING) as logs:
                response=await client.get('/synthetic/private-secret?token=sensitive')
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.headers['x-request-id'],response.json()['Reference'])
        text=' '.join(logs.output)
        for secret in ['private-secret','sensitive','password=never-log-this']:self.assertNotIn(secret,text+response.text)
        self.assertIn('/synthetic/{secret}',text)
