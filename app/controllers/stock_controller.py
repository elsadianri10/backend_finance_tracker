from fastapi import Response
from app.services import stock_service


async def execute(action, response: Response, *args):
    response.headers['Cache-Control'] = 'no-store'
    return await getattr(stock_service, action)(*args)
