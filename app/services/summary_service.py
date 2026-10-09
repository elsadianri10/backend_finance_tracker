from calendar import monthrange
from datetime import date
from sqlalchemy import select, func
from app.models.routine_model import LedgerTransaction
from app.models.billing_model import BillingAccount
from app.models.billing_transaction_model import BillingTransaction, BillingInstallment
from app.models.bank_account_model import BankAccount
from app.models.split_bill_model import SplitBillGroup
from app.services import routine_service, savings_service, debt_service
from app.services.billing_transaction_service import local_today, month_date, subscription_due


async def summary(user_id, month, db):
    start = date.fromisoformat(month + '-01')
    end = start.replace(day=monthrange(start.year, start.month)[1])
    today = local_today()
    rows = list(await db.scalars(select(LedgerTransaction).where(LedgerTransaction.user_id == user_id,
        LedgerTransaction.voided_at.is_(None), LedgerTransaction.transaction_date.between(start, end))))
    earnings = sum(row.amount for row in rows if row.kind == 'income' and row.category not in ('cash_withdrawal', 'receivable'))
    received = sum(row.amount for row in rows if row.kind == 'income' and row.category == 'receivable')
    expenses = sum(row.amount for row in rows if row.kind == 'expense')
    month_totals = dict(Earnings=earnings, Expenses=expenses, ReceivableReceived=received, NetCashflow=earnings+received-expenses,
        AllocationTransferred=sum(row.amount for row in rows if row.kind == 'transfer' and row.category == 'savings'),
        CashWithdrawn=sum(row.amount for row in rows if row.category == 'cash_withdrawal'), TransactionsCount=len(rows))
    savings = await savings_service.list_savings(user_id, db)
    assets = dict(CashBalance=0, DepositBalance=0, GoldGrams=0, SilverGrams=0, GoldValue=0, SilverValue=0, UnpricedMetalsCount=0)
    for item in savings:
        if item['Kind'] == 'CASH':
            assets['CashBalance'] += int(item['Balance'])
        elif item['Kind'] == 'DEPOSIT':
            assets['DepositBalance'] += int(item['Balance'])
        else:
            prefix = 'Silver' if item['MetalType'] == 'SILVER' else 'Gold'
            assets[prefix+'Grams'] += float(item['Balance'])
            assets[prefix+'Value'] += item['EstimatedValue'] or 0
            assets['UnpricedMetalsCount'] += int(item['EstimatedValue'] is None)
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
    bill_rows = (await db.execute(select(BillingTransaction, BillingInstallment).join(BillingAccount, BillingAccount.id==BillingTransaction.account_id)
        .outerjoin(BillingInstallment, BillingInstallment.transaction_id==BillingTransaction.id)
        .where(BillingAccount.user_id==user_id))).all()
    pending, grouped = [], {}
    for transaction, installment in bill_rows:
        grouped.setdefault(transaction.id, (transaction, {}))
        if installment:
            grouped[transaction.id][1][installment.sequence] = installment
            if installment.paid_at is None:
                pending.append(dict(Label=transaction.description, Date=installment.due_date.isoformat(), Amount=int(installment.amount)))
    # Project accrued subscriptions without inserting installments during this GET.
    for transaction, installments in grouped.values():
        if transaction.transaction_kind != 'SUBSCRIPTION':
            continue
        through = min(today, transaction.stopped_on) if transaction.stopped_on else today
        anchor = transaction.transaction_date or transaction.first_installment
        offset = max(installments, default=0)
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
    return dict(Month=month, AsOf=today.isoformat(), MonthTotals=month_totals, Savings=assets, Debts=balances,
        Routines=routine_totals, Bills=billing, Banks=bank_totals, SplitBillGroups=groups,
        NextRoutines=next_routines, NextBills=next_bills)
