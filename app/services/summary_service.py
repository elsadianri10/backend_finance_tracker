from calendar import monthrange
from datetime import date, timedelta
from sqlalchemy import and_, select, func, case
from app.models.routine_model import LedgerTransaction
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.models.bank_account_model import BankAccount
from app.models.savings_model import Saving, SavingMovement
from app.models.split_bill_model import SplitBillGroup
from app.services import routine_service, savings_service, debt_service
from app.services.billing_transaction_service import local_today, month_date, subscription_due


async def summary(user_id, month, db):
    start = date.fromisoformat(month + '-01')
    end = start.replace(day=monthrange(start.year, start.month)[1])
    today = local_today()
    def total(condition):
        return func.coalesce(func.sum(case((condition, LedgerTransaction.amount), else_=0)), 0)
    row = (await db.execute(select(
        total((LedgerTransaction.kind == 'income') & LedgerTransaction.category.not_in(('cash_withdrawal', 'receivable'))),
        total((LedgerTransaction.kind == 'income') & (LedgerTransaction.category == 'receivable')),
        total(LedgerTransaction.kind == 'expense'),
        total((LedgerTransaction.kind == 'transfer') & (LedgerTransaction.category == 'savings')),
        total(LedgerTransaction.category == 'cash_withdrawal'), func.count())
        .where(LedgerTransaction.user_id == user_id, LedgerTransaction.voided_at.is_(None),
               LedgerTransaction.transaction_date.between(start, end)))).one()
    earnings, received, expenses, allocation, withdrawn, count = map(int, row)
    month_totals = dict(Earnings=earnings, Expenses=expenses, ReceivableReceived=received, NetCashflow=earnings+received-expenses,
        AllocationTransferred=allocation, CashWithdrawn=withdrawn, TransactionsCount=count)
    balance = Saving.opening_amount + func.coalesce(func.sum(case(
        (SavingMovement.direction == 'ADD', SavingMovement.amount),
        else_=-SavingMovement.amount,
    )), 0)
    savings = await db.execute(select(Saving.kind, Saving.metal_type, Saving.price_per_gram, balance)
        .outerjoin(SavingMovement, SavingMovement.saving_id == Saving.id)
        .where(Saving.user_id == user_id)
        .group_by(Saving.id, Saving.kind, Saving.metal_type, Saving.price_per_gram, Saving.opening_amount)
        .order_by(Saving.name, Saving.id))
    assets: dict[str, int | float] = dict(CashBalance=0, DepositBalance=0, GoldGrams=0, SilverGrams=0, GoldValue=0, SilverValue=0, UnpricedMetalsCount=0)
    for kind, metal, price, amount in savings:
        if kind == 'CASH':
            assets['CashBalance'] += int(amount)
        elif kind == 'DEPOSIT':
            assets['DepositBalance'] += int(amount)
        else:
            prefix = 'Silver' if metal == 'SILVER' else 'Gold'
            estimated = savings_service.estimated_metal_value(kind, price, amount)
            assets[prefix+'Grams'] += float(amount)
            assets[prefix+'Value'] += estimated or 0
            assets['UnpricedMetalsCount'] += int(estimated is None)
    debts = await debt_service.list_debts(user_id, db)
    debts = [row for row in debts if not row['IsSettled']]
    balances = dict(Owed=sum(row['RemainingAmount'] for row in debts if row['Kind']=='DEBT'),
        Receivable=sum(row['RemainingAmount'] for row in debts if row['Kind']=='RECEIVABLE'),
        OverdueCount=sum(row['IsOverdue'] for row in debts), ActiveCount=len(debts))
    plans = await routine_service.list_plans(user_id, month, db)
    active = [row for row in plans if row['StoredStatus']=='ACTIVE']
    routine_totals = dict(Planned=sum(row['PlannedAmount'] for row in active), Paid=sum(row['PaidAmount'] for row in plans),
        Pending=sum(row['PendingAmount'] for row in active), ActiveCount=sum(row['Status']=='ACTIVE' for row in plans),
        NoteCount=sum(row['StoredStatus']=='NOTE' for row in plans))
    next_routines = sorted([dict(Id=row['Id'], Label=(row['Recipient']+' · ' if row['Recipient'] else '')+row['Name'],
        Date=row['NextDueDate'], Amount=row['Amount']) for row in plans if row['Status']=='ACTIVE' and row['NextDueDate']],
        key=lambda row: (row['Date'], row['Label'].casefold()))[:5]
    latest_sequence = select(func.max(BillingInstallment.sequence)).where(
        BillingInstallment.transaction_id == BillingTransaction.id,
    ).correlate(BillingTransaction).scalar_subquery()
    bill_rows = await db.execute(select(BillingTransaction, BillingInstallment.due_date, BillingInstallment.amount,
        case((BillingTransaction.transaction_kind == 'SUBSCRIPTION', latest_sequence)))
        .join(BillingAccount, BillingAccount.id == BillingTransaction.account_id)
        .outerjoin(BillingInstallment, and_(BillingInstallment.transaction_id == BillingTransaction.id,
                                            BillingInstallment.paid_at.is_(None)))
        .where(BillingAccount.user_id == user_id))
    pending, subscriptions = [], {}
    for transaction, due_date, amount, last_sequence in bill_rows:
        if due_date is not None:
            pending.append(dict(Label=transaction.description, Date=due_date.isoformat(), Amount=int(amount)))
        if transaction.transaction_kind == 'SUBSCRIPTION':
            subscriptions[transaction.id] = (transaction, last_sequence or 0)
    # Project accrued subscriptions without inserting installments during this GET.
    for transaction, offset in subscriptions.values():
        through = min(today, transaction.stopped_on) if transaction.stopped_on else today
        anchor = transaction.transaction_date or transaction.first_installment
        while True:
            charge = month_date(anchor, offset, anchor.day)
            if charge > through:
                break
            pending.append(dict(Label=transaction.description, Date=subscription_due(transaction, charge).isoformat(), Amount=int(transaction.amount)))
            offset += 1
    monthly_bills = [row for row in pending if row['Date'].startswith(month)]
    overdue = [row for row in pending if row['Date'] < today.isoformat()]
    billing = dict(PendingAmount=sum(row['Amount'] for row in monthly_bills), PendingCount=len(monthly_bills),
        OverdueAmount=sum(row['Amount'] for row in overdue), OverdueCount=len(overdue))
    relevant = [row for row in pending if row['Date'].startswith(month) or (month==today.strftime('%Y-%m') and row['Date']<today.isoformat())]
    next_bills = sorted(relevant, key=lambda row: (row['Date'],row['Label'].casefold()))[:5]
    bank_rows = list(await db.scalars(select(BankAccount).where(BankAccount.user_id==user_id)))
    bank_totals = dict(Count=len(bank_rows), MonthlyFees=sum(int(row.admin_fee+row.others_fee) for row in bank_rows))
    groups = await db.scalar(select(func.count()).select_from(SplitBillGroup).where(SplitBillGroup.user_id==user_id,
        SplitBillGroup.start_date<=end, SplitBillGroup.end_date>=start))
    from app.models import User, AccountAccess
    from app.services.access_service import status
    from app.services import stock_service
    access = status(await db.get(AccountAccess, user_id))
    reminders = []
    horizon = (today + timedelta(days=7)).isoformat()
    def due_reminder(kind, label, day, amount=None):
        day = day.isoformat() if hasattr(day, 'isoformat') else day
        if day and day <= horizon:
            reminders.append(dict(Kind=kind, Label=label, Date=day, Amount=amount,
                Severity='overdue' if day < today.isoformat() else 'today' if day == today.isoformat() else 'soon'))
    for item in plans:
        if item['Status']=='ACTIVE': due_reminder('routine', item['Name'], item['NextDueDate'], item['Amount'])
    if access['EffectivePlan'] == 'PRO':
        for item in pending: due_reminder('billing', item['Label'], item['Date'], item['Amount'])
        for item in debts:
            installments=[bill for bill in item.get('Installments',[]) if bill['RemainingPrincipal']>0]
            upcoming=min(installments,key=lambda bill:bill['DueDate']) if installments else None
            due_reminder('debts',item['PersonName'],upcoming['DueDate'] if upcoming else item.get('DueDate'),upcoming['RemainingPrincipal'] if upcoming else item['RemainingAmount'])
        user = await db.get(User,user_id)
        for need in await stock_service.listed(user,db):
            products=[p for p in need['Products'] if p['ReplenishmentEligible']]
            empty=bool(products) and all(p['ActiveCount']+p['ReserveCount']==0 for p in products)
            if need['BuyReason'] or empty:
                reminders.append(dict(Kind='stockNeeds',Label=need['Name'],Date=None,Amount=None,
                    Severity='empty' if empty else 'stock',Reason=need['BuyReason'] or 'empty'))
    reminders.sort(key=lambda item:(0 if item['Severity'] in {'overdue','empty'} else 1 if item['Severity']=='today' else 2,item['Date'] or today.isoformat(),item['Label'].casefold()))
    reminder_total=len(reminders)
    return dict(Reminders=reminders[:12],ReminderTotal=reminder_total,Month=month, AsOf=today.isoformat(), MonthTotals=month_totals, Savings=assets, Debts=balances,
        Routines=routine_totals, Bills=billing, Banks=bank_totals, SplitBillGroups=groups,
        NextRoutines=next_routines, NextBills=next_bills)
