import json
import logging
import unittest

from asyncpg.exceptions import UndefinedColumnError, UndefinedTableError
from fastapi import FastAPI
from httpx import AsyncClient,ASGITransport
from sqlalchemy.exc import ProgrammingError
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

    async def test_database_log_uses_sqlstate_without_query_or_parameters(self):
        app = FastAPI()
        app.add_middleware(RequestDiagnostics)

        class InvalidCode(Exception):
            sqlstate = 'secret-value'

        errors = {
            'table': UndefinedTableError('private driver message'),
            'column': UndefinedColumnError('private driver message'),
            'invalid': InvalidCode('private driver message'),
        }

        @app.get('/synthetic/{example}')
        async def fail(example: str):
            raise ProgrammingError('private statement', ('private parameter',), errors[example])

        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            for example, category, code in (
                ('table', 'database_missing_table', '42P01'),
                ('column', 'database_missing_column', '42703'),
                ('invalid', 'database', None),
            ):
                with self.subTest(example=example), self.assertLogs('finance.requests', level=logging.WARNING) as logs:
                    response = await client.get('/synthetic/' + example)
                    self.assertEqual(response.status_code, 500)
                    failure, result = [json.loads(record.getMessage()) for record in logs.records]
                    self.assertEqual(failure['category'], category)
                    self.assertEqual(failure.get('sqlstate'), code)
                    self.assertEqual(failure['route'], '/synthetic/{example}')
                    self.assertEqual(failure['reference'], result['reference'])
                    self.assertEqual(failure['reference'], response.headers['x-request-id'])
                    for secret in ('private driver message', 'private statement', 'private parameter', 'secret-value'):
                        self.assertNotIn(secret, str(logs.output) + response.text)
