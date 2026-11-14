"""Recover an ambiguous recurring setup using its existing merchant-dashboard ID; never creates a charge."""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID
from dotenv import load_dotenv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
load_dotenv('.env')
from app.config.db_config import async_session, engine
from app.models.subscription_model import SubscriptionOrder
from app.services import midtrans_service as gateway, subscription_service as service

async def run(args):
    try:
        async with async_session() as db:
            row=await db.get(SubscriptionOrder,args.order_id)
            if row is None or row.environment!=gateway.configuration()[0] or not row.setup_attempted_at:
                raise ValueError('Order tidak ditemukan atau tidak memiliki setup recurring pada environment ini')
            provider=await gateway.call('GET','/v1/subscriptions/'+gateway.identifier(args.provider_id))
            if provider.get('name')!=service.renewal_name(row) or not service.amount_matches(provider.get('amount'),row.amount) or provider.get('currency')!='IDR':
                raise ValueError('Langganan provider tidak cocok dengan order')
            print('Verified existing subscription:',str(row.id),provider.get('status'))
            if args.apply:
                await service.webhook(os.environ['MIDTRANS_WEBHOOK_TOKEN'],{'id':args.provider_id,'name':provider['name']},db)
                print('Reconciled. No new checkout, schedule or charge created.')
            else:
                print('Read-only. Add --apply to record this existing subscription and honor any pending cancellation.')
    finally:
        await engine.dispose()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('order_id',type=UUID)
    parser.add_argument('provider_id')
    parser.add_argument('--apply',action='store_true')
    asyncio.run(run(parser.parse_args()))
