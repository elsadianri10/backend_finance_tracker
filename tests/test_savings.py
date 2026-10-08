import unittest
from datetime import date
from unittest.mock import patch
from uuid import UUID, uuid4
from sqlalchemy import select
import test_billing as fixture
from app.models.savings_model import Saving, SavingMovement


class SavingsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def create(self, **changes):
        body = dict(Kind='CASH', Name='Dana Darurat', OpeningAmount=1000000, StartDate='2026-10-01', Notes='')
        body.update(changes)
        return await self.client.post('/savings', headers=self.headers, json=body)

    async def move(self, item, direction='ADD', amount='500000', **changes):
        payload = dict(RequestId=str(uuid4()), Direction=direction, Amount=amount, MovementDate='2026-10-08', Notes='') | changes
        return await self.client.post('/savings/'+item['Id']+'/movements', headers=self.headers, json=payload)

    async def test_cash_movements_order_overdraw_idempotency_and_locked_opening(self):
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            created = await self.create()
            self.assertEqual(created.status_code,201,created.text)
            item=created.json()
            request_id=str(uuid4())
            first=await self.move(item, RequestId=request_id)
            self.assertEqual(first.status_code,201,first.text)
            self.assertEqual(first.json()['Balance'],1500000)
            self.assertEqual((await self.move(item,RequestId=request_id)).json(),first.json())
            self.assertEqual((await self.move(item,amount='1',RequestId=request_id)).status_code,409)
            for changes in [dict(direction='REMOVE',amount='1500001'),dict(amount='1.5'),dict(MovementDate='2026-10-07'),dict(MovementDate='2026-10-09')]:
                self.assertEqual((await self.move(item,**changes)).status_code,422)
            payload=dict(Kind='CASH',Name='Updated',OpeningAmount=2,StartDate='2026-10-01')
            self.assertEqual((await self.client.patch('/savings/'+item['Id'],headers=self.headers,json=payload)).status_code,409)
            payload['OpeningAmount']=1000000
            self.assertEqual((await self.client.patch('/savings/'+item['Id'],headers=self.headers,json=payload)).status_code,200)
            final=await self.move(item,'REMOVE','1500000')
            self.assertEqual(final.json()['Balance'],0)
            self.assertEqual(len(final.json()['Movements']),2)

    async def test_gold_decimal_weight_valuation_and_hidden_fields(self):
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            item=await self.create(Kind='GOLD',OpeningAmount=None,WeightPerPiece='0.125',Pieces=3,PurchaseCost=400000,PricePerGram=1700000)
            self.assertEqual(item.status_code,201,item.text)
            item=item.json()
            self.assertEqual(item['MetalType'],'GOLD')
            self.assertEqual(item['Balance'],0.375)
            self.assertEqual(item['EstimatedValue'],637500)
            result=await self.move(item,amount='0.005')
            self.assertEqual(result.json()['Balance'],0.38)
            self.assertEqual(result.json()['EstimatedValue'],646000)
            self.assertEqual((await self.move(item,amount='0.0001')).status_code,422)
            self.assertEqual((await self.create(Kind='GOLD',WeightPerPiece=1,Pieces=1)).status_code,422)
            self.assertEqual((await self.create(WeightPerPiece=1,Pieces=1)).status_code,422)

    async def test_silver_valuation_legacy_update_and_metal_lock(self):
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            created=await self.create(Kind='GOLD',MetalType='SILVER',OpeningAmount=None,WeightPerPiece=50,Pieces=2,PricePerGram=25000)
            self.assertEqual(created.status_code,201,created.text)
            item=created.json()
            self.assertEqual(item['MetalType'],'SILVER')
            self.assertEqual(item['Balance'],100)
            self.assertEqual(item['EstimatedValue'],2500000)
            moved=await self.move(item,amount='0.125')
            self.assertEqual(moved.json()['Balance'],100.125)
            self.assertEqual(moved.json()['EstimatedValue'],2503125)
            payload=dict(Kind='GOLD',Name='Updated Silver',StartDate='2026-10-01',WeightPerPiece=50,Pieces=2,PricePerGram=30000)
            updated=await self.client.patch('/savings/'+item['Id'],headers=self.headers,json=payload)
            self.assertEqual(updated.status_code,200,updated.text)
            self.assertEqual(updated.json()['MetalType'],'SILVER')
            self.assertEqual(updated.json()['EstimatedValue'],3003750)
            payload['MetalType']='GOLD'
            self.assertEqual((await self.client.patch('/savings/'+item['Id'],headers=self.headers,json=payload)).status_code,409)
            gold=(await self.create(Kind='GOLD',OpeningAmount=None,WeightPerPiece=1,Pieces=1)).json()
            listed=(await self.client.get('/savings',headers=self.headers)).json()
            self.assertEqual({row['Id']:row['MetalType'] for row in listed}, {item['Id']:'SILVER',gold['Id']:'GOLD'})

    async def test_metal_type_only_valid_for_metals(self):
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            for changes in (dict(MetalType='SILVER'),dict(Kind='GOLD',MetalType='PLATINUM',OpeningAmount=None,WeightPerPiece=1,Pieces=1),dict(Kind='GOLD',MetalType=None,OpeningAmount=None,WeightPerPiece=1,Pieces=1)):
                self.assertEqual((await self.create(**changes)).status_code,422)
            cash=(await self.create()).json()
            self.assertIsNone(cash['MetalType'])

    async def test_price_date_changes_only_with_price(self):
        payload=dict(Kind='GOLD',Name='Silver',StartDate='2026-10-01',MetalType='SILVER',WeightPerPiece=50,Pieces=2,PricePerGram=25000)
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            created=await self.client.post('/savings',headers=self.headers,json=payload)
            self.assertEqual(created.status_code,201,created.text)
            item=created.json()
            self.assertEqual(item['PriceDate'],'2026-10-08')
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,9)):
            self.assertEqual((await self.move(item,amount='1',MovementDate='2026-10-09')).json()['PriceDate'],'2026-10-08')
            path='/savings/'+item['Id']
            payload.update(Name='Renamed',Notes='Metadata edit',PurchaseCost=2000000)
            updated=await self.client.patch(path,headers=self.headers,json=payload)
            self.assertEqual(updated.status_code,200,updated.text)
            self.assertEqual(updated.json()['PriceDate'],'2026-10-08')
            payload['PricePerGram']=26000
            updated=await self.client.patch(path,headers=self.headers,json=payload)
            self.assertEqual(updated.json()['PriceDate'],'2026-10-09')
            # An unchanged legacy price must not get an invented historical date.
            async with self.sessions() as db:
                old=await db.get(Saving,UUID(item['Id']))
                old.price_date=None
                await db.commit()
            self.assertIsNone((await self.client.patch(path,headers=self.headers,json=payload)).json()['PriceDate'])
            payload['PricePerGram']=27000
            self.assertEqual((await self.client.patch(path,headers=self.headers,json=payload)).json()['PriceDate'],'2026-10-09')
            payload['PricePerGram']=None
            self.assertIsNone((await self.client.patch(path,headers=self.headers,json=payload)).json()['PriceDate'])
            payload['PricePerGram']=28000
            self.assertEqual((await self.client.patch(path,headers=self.headers,json=payload)).json()['PriceDate'],'2026-10-09')
            self.assertIsNone((await self.create()).json()['PriceDate'])

    async def test_bank_ownership_deposit_snapshot_and_no_auto_interest(self):
        with patch('app.services.savings_service.local_today', return_value=date(2026,10,8)):
            bank=await self.client.post('/bank-accounts',headers=self.headers,json=dict(PlatformId=1,AccountNumber='0123456789',CardNumber='0123456789012345',ValidThru='2029-07'))
            self.assertEqual(bank.status_code,201,bank.text)
            payload=dict(Kind='DEPOSIT',BankAccountId=bank.json()['Id'],MaturityDate='2027-10-01',InterestRate='4.25')
            deposit=await self.create(**payload)
            self.assertEqual(deposit.status_code,201,deposit.text)
            item=deposit.json()
            self.assertEqual(item['Balance'],1000000)
            self.assertEqual(item['BankName'],'BCA')
            self.assertNotIn('0123456789',deposit.text)
            other=await self.client.post('/savings',headers=self.auth_headers(self.other_id),json=dict(Kind='CASH',Name='Other',OpeningAmount=10,StartDate='2026-10-01',BankAccountId=bank.json()['Id']))
            self.assertEqual(other.status_code,422)
            self.assertEqual((await self.create(Kind='DEPOSIT',MaturityDate='2027-01-01')).status_code,422)
            await self.client.delete('/bank-accounts/'+bank.json()['Id'],headers=self.headers)
            detail=(await self.client.get('/savings/'+item['Id'],headers=self.headers)).json()
            self.assertIsNone(detail['BankAccountId'])
            self.assertEqual(detail['BankName'],'BCA')
            self.assertEqual(detail['BankAccountMasked'],item['BankAccountMasked'])

    async def test_access_list_delete_and_validation(self):
        with patch('app.services.savings_service.local_today',return_value=date(2026,10,8)):
            item=(await self.create()).json()
            await self.move(item)
            path='/savings/'+item['Id']
            other=self.auth_headers(self.other_id)
            for method in ('get','patch','delete'):
                kwargs=dict(headers=other)
                if method=='patch':kwargs['json']=dict(Kind='CASH',Name='Other',OpeningAmount=1,StartDate='2026-10-01')
                self.assertEqual((await getattr(self.client,method)(path,**kwargs)).status_code,404)
            self.assertEqual((await self.client.get('/savings')).status_code,401)
            self.assertEqual((await self.client.get('/savings',headers=other)).json(),[])
            listed=await self.client.get('/savings',headers=self.headers)
            self.assertEqual(listed.headers['cache-control'],'no-store')
            self.assertEqual(len(listed.json()),1)
            for changes in (dict(Name=' '),dict(OpeningAmount=True),dict(StartDate='2026-10-09'),dict(MaturityDate='2027-01-01')):
                self.assertEqual((await self.create(**changes)).status_code,422)
            self.assertEqual((await self.client.delete(path,headers=self.headers)).status_code,204)
            async with self.sessions() as db:
                self.assertEqual(list((await db.scalars(select(Saving))).all()),[])
                self.assertEqual(list((await db.scalars(select(SavingMovement))).all()),[])
