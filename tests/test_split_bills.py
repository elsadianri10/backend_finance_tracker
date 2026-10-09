import unittest
from uuid import uuid4
from fastapi import HTTPException
from app.schemas.split_bill_schema import GroupCreate
from app.services.split_bill_service import calculate, allocate
import test_billing as fixture


def example(count=3):
    people = [{'Id': str(uuid4()), 'Name': f'Person {i+1}'} for i in range(count)]
    return {'Name': 'Shared expenses', 'StartDate': '2026-10-01', 'EndDate': '2026-10-31', 'Participants': people, 'Expenses': []}


def expense(body, amount=100000, members=None, payer=0):
    ids = [p['Id'] for p in body['Participants']]
    return {'Id': str(uuid4()), 'Name': 'Dinner', 'ExpenseDate': '2026-10-09', 'PaidBy': ids[payer], 'Items': [{'Id': str(uuid4()), 'Name': 'Shared food', 'Amount': amount, 'SplitMode': 'EQUAL', 'Shares': [{'ParticipantId': ids[i], 'Amount': 0} for i in (members if members is not None else range(len(ids)))]}], 'ServiceCharge': {'Mode': 'AMOUNT', 'Value': 0}, 'Tax': {'Mode': 'AMOUNT', 'Value': 0}, 'TaxIncludesService': False, 'FeeAllocation': 'PROPORTIONAL', 'Notes': ''}


class CalculationTests(unittest.TestCase):
    def test_service_equal_all_and_tax_from_consumption_plus_service(self):
        body = example(3)
        bill = expense(body, 100000, [0, 1])
        bill['Items'][0]['SplitMode'] = 'CUSTOM'
        bill['Items'][0]['Shares'][0]['Amount'] = 60000
        bill['Items'][0]['Shares'][1]['Amount'] = 40000
        bill['ServiceCharge'] = {'Mode': 'AMOUNT', 'Value': 30000}
        bill['Tax'] = {'Mode': 'PERCENT', 'Value': 10}
        del bill['FeeAllocation']
        del bill['TaxIncludesService']
        body['Expenses'] = [bill]
        result = calculate(GroupCreate.model_validate(body))
        self.assertEqual([row['ServiceCharge'] for row in result['Participants']], [10000]*3)
        self.assertEqual([row['Tax'] for row in result['Participants']], [7000, 5000, 1000])
        self.assertEqual(result['Total'], 143000)
        # MIXED always includes service even if an older client sends false.
        bill['FeeAllocation'] = 'MIXED'
        bill['TaxIncludesService'] = False
        self.assertEqual(calculate(GroupCreate.model_validate(body)), result)
        bill['ServiceCharge']['Value'] = 1
        bill['Tax'] = {'Mode': 'AMOUNT', 'Value': 7}
        result = calculate(GroupCreate.model_validate(body))
        self.assertEqual(sum(row['ServiceCharge'] for row in result['Participants']), 1)
        self.assertEqual(sum(row['Tax'] for row in result['Participants']), 7)
        self.assertEqual(sum(row['Total'] for row in result['Participants']), 100008)

    def test_receipt_total_rounding_and_settlement(self):
        body = example(2)
        bill = expense(body, 150400)
        bill['FeeAllocation'] = 'MIXED'
        bill['Items'][0]['SplitMode'] = 'CUSTOM'
        bill['Items'][0]['Shares'][0]['Amount'] = 82600
        bill['Items'][0]['Shares'][1]['Amount'] = 67800
        bill['ServiceCharge'] = {'Mode': 'AMOUNT', 'Value': 10528}
        bill['Tax'] = {'Mode': 'AMOUNT', 'Value': 16093}
        body['Expenses'] = [bill]
        original = calculate(GroupCreate.model_validate(body))
        self.assertEqual(original['Total'], 177021)
        for target in (177000, 177050, 0, 1, 177021):
            bill['ReceiptTotal'] = target
            result = calculate(GroupCreate.model_validate(body))
            self.assertEqual(result['Total'], target)
            row = result['Expenses'][0]
            self.assertEqual(row['BeforeAdjustment'], 177021)
            self.assertEqual(row['Adjustment'], target - 177021)
            self.assertEqual(sum(p['Adjustment'] for p in row['Participants']), row['Adjustment'])
            self.assertEqual(sum(p['Total'] for p in row['Participants']), target)
            self.assertTrue(all(p['Total'] >= 0 for p in row['Participants']))
            self.assertEqual(sum(p['Paid'] for p in result['Participants']), target)
            self.assertEqual(sum(p['Balance'] for p in result['Participants']), 0)
        bill['ReceiptTotal'] = None
        self.assertEqual(calculate(GroupCreate.model_validate(body)), original)
        from pydantic import ValidationError
        for value in (-1, True, 1.5, 1000000000001):
            bill['ReceiptTotal'] = value
            with self.assertRaises(ValidationError):
                GroupCreate.model_validate(body)

    def test_twenty_people_remainders_and_transfer_conservation(self):
        body = example(20)
        body['Expenses'] = [expense(body, 100001), expense(body, 50003, [0, 1, 5, 18], 19)]
        result = calculate(GroupCreate.model_validate(body))
        self.assertEqual(result['Total'],150004)
        self.assertEqual(sum(row['Total'] for row in result['Participants']),result['Total'])
        self.assertEqual(sum(row['Balance'] for row in result['Participants']),0)
        balances = {row['ParticipantId']:row['Balance'] for row in result['Participants']}
        for transfer in result['Transfers']:
            balances[transfer['FromParticipantId']] += transfer['Amount']
            balances[transfer['ToParticipantId']] -= transfer['Amount']
        self.assertTrue(all(value == 0 for value in balances.values()))
        self.assertLessEqual(len(result['Transfers']),19)
        for amount in range(1,100):
            split = allocate(amount,{str(i):i+1 for i in range(20)})
            self.assertEqual(sum(split.values()),amount)

    def test_custom_consumption_tax_base_and_fee_allocation(self):
        body=example()
        bill=expense(body,100000,[0,1])
        bill['Items'][0]['SplitMode']='CUSTOM'
        bill['Items'][0]['Shares'][0]['Amount']=30000
        bill['Items'][0]['Shares'][1]['Amount']=70000
        bill['ServiceCharge']={'Mode':'PERCENT','Value':'5'}
        bill['Tax']={'Mode':'PERCENT','Value':'10'}
        body['Expenses']=[bill]
        result=calculate(GroupCreate.model_validate(body))
        self.assertEqual([row['Total'] for row in result['Participants']],[34500,80500,0])
        bill['TaxIncludesService']=True
        result=calculate(GroupCreate.model_validate(body))
        self.assertEqual(result['Total'],115500)
        bill['FeeAllocation']='EQUAL'
        result=calculate(GroupCreate.model_validate(body))
        self.assertEqual([row['Total'] for row in result['Participants']],[37750,77750,0])

    def test_invalid_references_duplicate_ids_and_custom_sum(self):
        for change in ('payer','shares','custom','date','person','item'):
            body=example(); bill=expense(body); body['Expenses']=[bill]
            if change=='payer':bill['PaidBy']=str(uuid4())
            if change=='shares':bill['Items'][0]['Shares'][0]['ParticipantId']=str(uuid4())
            if change=='custom':bill['Items'][0]['SplitMode']='CUSTOM'
            if change=='date':bill['ExpenseDate']='2026-11-01'
            if change=='person':body['Participants'][1]['Id']=body['Participants'][0]['Id']
            if change=='item':bill['Items'].append(bill['Items'][0])
            with self.assertRaises(HTTPException) as error:calculate(GroupCreate.model_validate(body))
            self.assertEqual(error.exception.status_code,422)


class SplitBillApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixture.BillingTests.asyncSetUp
    asyncTearDown = fixture.BillingTests.asyncTearDown
    auth_headers = fixture.BillingTests.auth_headers

    async def test_crud_ownership_conflicts_and_no_store(self):
        body=example();body['Expenses']=[expense(body)]
        created=await self.client.post('/split-bills',headers=self.headers,json=body)
        self.assertEqual(created.status_code,201,created.text)
        item=created.json();self.assertEqual(item['Version'],1)
        self.assertNotIn('UserId',item)
        path='/split-bills/'+item['Id']
        pdf = await self.client.get(path+'/export',headers=self.headers)
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        self.assertEqual(pdf.headers['cache-control'],'no-store')
        self.assertIn('attachment',pdf.headers['content-disposition'])
        self.assertEqual((await self.client.get(path+'/export')).status_code,401)
        self.assertEqual((await self.client.get(path+'/export',headers=self.auth_headers(self.other_id))).status_code,404)
        self.assertEqual((await self.client.get('/split-bills')).status_code,401)
        self.assertEqual((await self.client.get(path,headers=self.auth_headers(self.other_id))).status_code,404)
        listed=await self.client.get('/split-bills',headers=self.headers)
        self.assertEqual(listed.headers['cache-control'],'no-store')
        self.assertEqual(listed.json()[0]['Calculation']['Total'],100000)
        body['Name']='Edited'
        updated=await self.client.patch(path,headers=self.headers,json=body|{'Version':1})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(updated.json()['Version'],2)
        self.assertEqual((await self.client.patch(path,headers=self.headers,json=body|{'Version':1})).status_code,409)
        self.assertEqual((await self.client.delete(path,headers=self.auth_headers(self.other_id))).status_code,404)
        self.assertEqual((await self.client.delete(path,headers=self.headers)).status_code,204)
        self.assertEqual((await self.client.get('/split-bills',headers=self.headers)).json(),[])

    async def test_participant_limits_and_strict_amounts(self):
        for count in (1,21):
            result=await self.client.post('/split-bills',headers=self.headers,json=example(count))
            self.assertEqual(result.status_code,422)
        valid=await self.client.post('/split-bills',headers=self.headers,json=example(20))
        self.assertEqual(valid.status_code,201,valid.text)
        for amount in (True,1.5,-1,0,1000000000001):
            body=example();body['Expenses']=[expense(body,amount)]
            self.assertEqual((await self.client.post('/split-bills',headers=self.headers,json=body)).status_code,422)
        body=example();body['Expenses']=[expense(body)];body['Expenses'][0]['Tax']={'Mode':'PERCENT','Value':101}
        self.assertEqual((await self.client.post('/split-bills',headers=self.headers,json=body)).status_code,422)

    async def test_relational_roundtrip_replacement_and_cascade(self):
        from sqlalchemy import select, func
        from app.models.split_bill_model import SplitBillParticipant, SplitBillExpense, SplitBillItem, SplitBillShare
        body = example(3)
        body['Participants'].reverse()
        first, second = expense(body, 10001), expense(body, 15003, [2, 0], 1)
        # Item IDs were only unique within an expense in the original API.
        second['Items'][0]['Id'] = first['Items'][0]['Id']
        first['Items'][0]['Shares'].reverse()
        second['ReceiptTotal'] = 15000
        body['Expenses'] = [second, first]
        created = await self.client.post('/split-bills', headers=self.headers, json=body)
        self.assertEqual(created.status_code, 201, created.text)
        result = created.json()
        path = '/split-bills/' + result['Id']
        loaded = (await self.client.get(path, headers=self.headers)).json()
        self.assertEqual(loaded, result)
        self.assertEqual(loaded['Calculation'], calculate(GroupCreate.model_validate(body)))
        self.assertEqual([r['Id'] for r in loaded['Participants']], [r['Id'] for r in body['Participants']])
        self.assertEqual([r['Id'] for r in loaded['Expenses']], [r['Id'] for r in body['Expenses']])
        self.assertEqual(loaded['Expenses'][1]['Items'][0]['Shares'], first['Items'][0]['Shares'])
        invalid = body | {'Version': 1, 'Expenses': [expense(body, 10000)]}
        invalid['Expenses'][0]['PaidBy'] = str(uuid4())
        self.assertEqual((await self.client.patch(path, headers=self.headers, json=invalid)).status_code, 422)
        self.assertEqual((await self.client.get(path, headers=self.headers)).json(), result)
        # Same client IDs in a second group must remain independent.
        other = await self.client.post('/split-bills', headers=self.headers, json=body)
        self.assertEqual(other.status_code, 201, other.text)
        body['Expenses'] = []
        body['Participants'] = body['Participants'][:2]
        updated = await self.client.patch(path, headers=self.headers, json=body | {'Version': 1})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['Expenses'], [])
        self.assertEqual(updated.json()['Calculation']['Total'], 0)
        self.assertEqual((await self.client.delete(path, headers=self.headers)).status_code, 204)
        self.assertEqual((await self.client.delete('/split-bills/' + other.json()['Id'], headers=self.headers)).status_code, 204)
        async with self.sessions() as db:
            for model in (SplitBillParticipant, SplitBillExpense, SplitBillItem, SplitBillShare):
                self.assertEqual(await db.scalar(select(func.count()).select_from(model)), 0)
