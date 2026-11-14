"""Structured request diagnostics without URL values, payloads or exception text."""
import json
import logging
from time import perf_counter
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
logger=logging.getLogger('finance.requests')
class RequestDiagnostics(BaseHTTPMiddleware):
    async def dispatch(self,request,call_next):
        reference=uuid4().hex;started=perf_counter();request.state.reference=reference
        try:
            response=await call_next(request)
        except Exception as exc:
            route=getattr(request.scope.get('route'),'path','unmatched')
            logger.error(json.dumps({'event':'request_failed','reference':reference,'route':route,'method':request.method,'type':type(exc).__name__}))
            response=JSONResponse({'detail':'Terjadi gangguan layanan','Reference':reference},status_code=500,headers={'Cache-Control':'no-store'})
        response.headers['X-Request-ID']=reference
        duration=round((perf_counter()-started)*1000)
        if response.status_code>=500 or duration>=2000:
            route=getattr(request.scope.get('route'),'path','unmatched')
            logger.warning(json.dumps({'event':'request_result','reference':reference,'route':route,'method':request.method,'status':response.status_code,'duration_ms':duration}))
        return response
