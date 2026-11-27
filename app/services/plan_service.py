"""Canonical plan capabilities and active-slot counts, shared by checks and UI."""
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.models import AccountAccess, User, BankAccount, Saving, RoutinePlan, RoutinePayment, LedgerTransaction, SplitBillGroup
from app.services.access_service import status, require_pro

FREE_LIMITS = {'bankAccounts': 3, 'savings': 3, 'routine': 3, 'splitBills': 2}
PRO_MENUS = ['billing', 'debts', 'bankAccounts', 'savings', 'routine', 'splitBills', 'wishlist', 'stockNeeds', 'budgeting', 'patungan']


def active_routines(user_id):
    paid = select(func.count(RoutinePayment.id)).join(LedgerTransaction, LedgerTransaction.routine_payment_id == RoutinePayment.id).where(RoutinePayment.plan_id == RoutinePlan.id).correlate(RoutinePlan).scalar_subquery()
    return select(RoutinePlan.id).where(RoutinePlan.user_id == user_id, RoutinePlan.status == 'ACTIVE',
        (RoutinePlan.total_cycles == 0) | (RoutinePlan.initial_paid + paid < RoutinePlan.total_cycles))


def active_query(feature, user_id):
    if feature == 'routine': return active_routines(user_id)
    if feature == 'splitBills':
        return select(SplitBillGroup.id).where(SplitBillGroup.user_id == user_id,
            SplitBillGroup.end_date >= datetime.now(ZoneInfo('Asia/Jakarta')).date())
    model = {'bankAccounts': BankAccount, 'savings': Saving}[feature]
    return select(model.id).where(model.user_id == user_id, model.archived.is_(False))


async def count_active(feature, user_id, db):
    return await db.scalar(select(func.count()).select_from(active_query(feature, user_id).subquery())) or 0


async def check_new_slot(feature, user_id, db):
    # Serialize all slot increases per account, including concurrent restores.
    await db.scalar(select(User.id).where(User.id == user_id).with_for_update())
    if await count_active(feature, user_id, db) >= FREE_LIMITS[feature]:
        await require_pro(user_id, db)


async def usage(user, db):
    access = status(await db.get(AccountAccess, user.id))
    pro = access['EffectivePlan'] == 'PRO'
    return {'EffectivePlan': access['EffectivePlan'], 'Source': access['Source'], 'ProMenus': PRO_MENUS,
        'Items': [{'Feature': key, 'Used': await count_active(key, user.id, db),
                   'FreeLimit': limit, 'Limit': None if pro else limit} for key, limit in FREE_LIMITS.items()]}


def catalog():
    from app.services.subscription_service import PRICES
    return {'MonthlyAmount': PRICES['MONTHLY'], 'AnnualAmount': PRICES['ANNUAL'], 'TrialDays': 30,
        'FreeLimits': FREE_LIMITS, 'ProMenus': PRO_MENUS,
        'Features': [
            {'Key':'transactions','Free':'FULL','Pro':'FULL'},
            {'Key':'security','Free':'FULL','Pro':'FULL'},
            {'Key':'billing','Free':'UNAVAILABLE','Pro':'FULL'},
            {'Key':'debts','Free':'UNAVAILABLE','Pro':'FULL'},
            {'Key':'bankAccounts','Free':'LIMITED','Pro':'EXPANDED'},
            {'Key':'savings','Free':'LIMITED','Pro':'EXPANDED'},
            {'Key':'routine','Free':'LIMITED','Pro':'EXPANDED'},
            {'Key':'splitBills','Free':'LIMITED','Pro':'EXPANDED'},
            {'Key':'splitPdf','Free':'UNAVAILABLE','Pro':'FULL'},
            {'Key':'wishlist','Free':'SHARED_GIFTS','Pro':'FULL'},
            {'Key':'stockNeeds','Free':'UNAVAILABLE','Pro':'FULL'},
            {'Key':'budgeting','Free':'UNAVAILABLE','Pro':'FULL'},
            {'Key':'patungan','Free':'UNAVAILABLE','Pro':'FULL'},
        ]}
