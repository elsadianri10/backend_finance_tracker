import unittest
from datetime import date,timedelta
from unittest.mock import patch
from uuid import uuid4
import test_billing as fixture
from app.models import AccountAccess,StockNeed,StockProduct,Debt,User
class ReminderTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=fixture.BillingTests.asyncSetUp
    asyncTearDown=fixture.BillingTests.asyncTearDown
    auth_headers=fixture.BillingTests.auth_headers
    async def test_empty_stock_pause_skip_and_due_wib(self):
        day=date(2026,11,3)
        async with self.sessions() as db:
            db.add(AccountAccess(user_id=self.user_id,complimentary=True))
            for name,paused,skip in [('Empty',False,None),('Paused',True,None),('Skipped',False,day+timedelta(days=1))]:
                need=StockNeed(id=uuid4(),user_id=self.user_id,name=name,category='health',subcategory='Vitamin',mode='manual',reserve_threshold=0,paused=False,archived=False,buy_requested=False,notes='',version=1)
                db.add(need);await db.flush()
                db.add(StockProduct(need_id=need.id,brand='Synthetic',variant='',package_unit='botol',package_size='',preference='staple',active_count=0,reserve_count=0,near_empty=False,archived=False,version=1,replenishment_paused=paused,replenishment_snoozed_until=skip))
            db.add(Debt(user_id=self.user_id,kind='DEBT',person_name='Due today',principal=1000,transaction_date=day-timedelta(days=1),due_date=day,interest_type='NONE',interest_rate=0,installment_count=0,notes=''))
            await db.commit()
        with patch('app.services.summary_service.local_today',return_value=day),patch('app.services.stock_service.today',return_value=day):
            response=await self.client.get('/summary?month=2026-11',headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            rows=response.json()['Reminders'];self.assertEqual({row['Label'] for row in rows},{'Empty','Due today'})
            self.assertEqual(next(r for r in rows if r['Label']=='Empty')['Severity'],'empty')
            self.assertEqual(next(r for r in rows if r['Label']=='Due today')['Severity'],'today')
            foreign=await self.client.get('/summary?month=2026-11',headers=self.auth_headers(self.other_id));self.assertEqual(foreign.json()['Reminders'],[])
