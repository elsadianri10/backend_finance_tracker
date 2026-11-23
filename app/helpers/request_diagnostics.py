"""Structured request diagnostics without URL values, payloads or exception text."""
import json
import logging
import re
from time import perf_counter
from uuid import uuid4

from asyncpg import PostgresError
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger=logging.getLogger('finance.requests')


def failure_details(exc):
    details = {'type': type(exc).__name__}
    if isinstance(exc, DBAPIError):
        original = exc.orig
    elif isinstance(exc, PostgresError):
        original = exc
    else:
        if isinstance(exc, SQLAlchemyError):
            details['category'] = 'database'
        return details

    code = getattr(original, 'sqlstate', None) or getattr(original, 'pgcode', None)
    if isinstance(code, str) and re.fullmatch(r'[0-9A-Z]{5}', code):
        details['sqlstate'] = code
        details['category'] = {
            '42P01': 'database_missing_table',
            '42703': 'database_missing_column',
        }.get(code, 'database')
        if code.startswith('08'):
            details['category'] = 'database_connection'
        elif code.startswith('23'):
            details['category'] = 'database_integrity'
    else:
        details['category'] = 'database'
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        details['category'] = 'database_connection'
    return details


class RequestDiagnostics(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        reference=uuid4().hex;started=perf_counter();request.state.reference=reference
        try:
            response=await call_next(request)
        except Exception as exc:
            route=getattr(request.scope.get('route'),'path','unmatched')
            logger.error(json.dumps({'event':'request_failed','reference':reference,'route':route,'method':request.method,**failure_details(exc)}))
            response=JSONResponse({'detail':'Terjadi gangguan layanan','Reference':reference},status_code=500,headers={'Cache-Control':'no-store'})
        response.headers['X-Request-ID']=reference
        duration=round((perf_counter()-started)*1000)
        if response.status_code>=500 or duration>=2000:
            route=getattr(request.scope.get('route'),'path','unmatched')
            logger.warning(json.dumps({'event':'request_result','reference':reference,'route':route,'method':request.method,'status':response.status_code,'duration_ms':duration}))
        return response
