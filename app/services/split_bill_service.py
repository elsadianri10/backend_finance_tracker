from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import select, delete, insert
from app.models.split_bill_model import SplitBillGroup, SplitBillParticipant, SplitBillExpense, SplitBillItem, SplitBillShare
from app.schemas.split_bill_schema import GroupCreate


def invalid(path, message):
    raise HTTPException(422, [{'loc': ['body', *path], 'msg': message, 'type': 'value_error'}])


def allocate(total, weights):
    """Largest remainder in integer rupiah. Ties follow participant order."""
    weight_sum = sum(weights.values())
    if not weight_sum:
        return {key: 0 for key in weights}
    result = {key: total * weight // weight_sum for key, weight in weights.items()}
    remainder = total - sum(result.values())
    order = sorted(weights, key=lambda key: -(total * weights[key] % weight_sum))
    for key in order[:remainder]:
        result[key] += 1
    return result


def charge_amount(charge, base):
    return int(charge.value) if charge.mode == 'AMOUNT' else int((Decimal(base) * charge.value / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def calculate(payload):
    if payload.end_date < payload.start_date:
        invalid(['EndDate'], 'Tanggal akhir tidak boleh sebelum tanggal mulai')
    ids = [str(p.id) for p in payload.participants]
    if len(set(ids)) != len(ids):
        invalid(['Participants'], 'ID peserta harus unik')
    if len({p.name.casefold() for p in payload.participants}) != len(ids):
        invalid(['Participants'], 'Nama peserta harus berbeda agar mudah dibedakan')
    summary = {key: {'ParticipantId': key, 'Subtotal': 0, 'ServiceCharge': 0, 'Tax': 0, 'Adjustment': 0, 'Total': 0, 'Paid': 0, 'Balance': 0} for key in ids}
    expense_results = []
    seen_expenses = set()
    for index, expense in enumerate(payload.expenses):
        path = ['Expenses', index]
        if expense.id in seen_expenses:
            invalid(path + ['Id'], 'ID pengeluaran harus unik')
        seen_expenses.add(expense.id)
        if not payload.start_date <= expense.expense_date <= payload.end_date:
            invalid(path + ['ExpenseDate'], 'Tanggal pengeluaran harus dalam periode grup')
        payer = str(expense.paid_by)
        if payer not in summary:
            invalid(path + ['PaidBy'], 'Pilih pembayar dari peserta grup')
        subtotals = dict.fromkeys(ids, 0)
        seen_items = set()
        for item_index, item in enumerate(expense.items):
            item_path = path + ['Items', item_index]
            if item.id in seen_items:
                invalid(item_path + ['Id'], 'ID item harus unik')
            seen_items.add(item.id)
            share_ids = [str(share.participant_id) for share in item.shares]
            if len(set(share_ids)) != len(share_ids) or any(key not in summary for key in share_ids):
                invalid(item_path + ['Shares'], 'Pilih peserta yang valid tanpa duplikasi')
            shares = {key: next(share.amount for share in item.shares if str(share.participant_id) == key) for key in ids if key in share_ids}
            if item.split_mode == 'CUSTOM':
                if sum(shares.values()) != item.amount:
                    invalid(item_path + ['Shares'], 'Jumlah nominal peserta harus sama dengan harga item')
            else:
                shares = allocate(item.amount, {key: 1 for key in shares})
            for key, amount in shares.items():
                subtotals[key] += amount
        subtotal = sum(subtotals.values())
        service = charge_amount(expense.service_charge, subtotal)
        mixed = expense.fee_allocation == 'MIXED'
        tax = charge_amount(expense.tax, subtotal + (service if mixed or expense.tax_includes_service else 0))
        total = subtotal + service + tax
        if total > 1000000000000:
            invalid(path + ['Items'], 'Total pengeluaran maksimal Rp 1 triliun')
        weights = {key: amount if expense.fee_allocation == 'PROPORTIONAL' else 1 for key, amount in subtotals.items() if amount > 0}
        if mixed:
            services = allocate(service, dict.fromkeys(ids, 1))
            taxes = allocate(tax, {key: subtotals[key] + services[key] for key in ids})
        else:
            services, taxes = allocate(service, weights), allocate(tax, weights)
        before_adjustment = total
        base_parts = {key: subtotals[key] + services.get(key, 0) + taxes.get(key, 0) for key in ids}
        if expense.receipt_total is not None:
            total = expense.receipt_total
        final_parts = allocate(total, base_parts) if total != before_adjustment else base_parts
        parts = []
        for key in ids:
            part = {'ParticipantId': key, 'Subtotal': subtotals[key], 'ServiceCharge': services.get(key, 0), 'Tax': taxes.get(key, 0)}
            part['Adjustment'] = final_parts[key] - base_parts[key]
            part['Total'] = final_parts[key]
            parts.append(part)
            for field in ('Subtotal', 'ServiceCharge', 'Tax', 'Adjustment', 'Total'):
                summary[key][field] += part[field]
        summary[payer]['Paid'] += total
        expense_results.append({'Id': str(expense.id), 'Subtotal': subtotal, 'ServiceCharge': service, 'Tax': tax, 'BeforeAdjustment': before_adjustment, 'Adjustment': total - before_adjustment, 'Total': total, 'Participants': parts})
    total = sum(row['Total'] for row in summary.values())
    if total > 1000000000000:
        invalid(['Expenses'], 'Total grup maksimal Rp 1 triliun')
    for row in summary.values():
        row['Balance'] = row['Paid'] - row['Total']
    creditors = [[key, row['Balance']] for key, row in summary.items() if row['Balance'] > 0]
    debtors = [[key, -row['Balance']] for key, row in summary.items() if row['Balance'] < 0]
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])
        transfers.append({'FromParticipantId': debtors[i][0], 'ToParticipantId': creditors[j][0], 'Amount': amount})
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return {'Total': total, 'Participants': list(summary.values()), 'Expenses': expense_results, 'Transfers': transfers}


async def responses(groups, db):
    """Load each child table once, including when listing many groups."""
    if not groups:
        return []
    ids = [group.id for group in groups]
    documents = {group.id: {'Name': group.name, 'StartDate': group.start_date, 'EndDate': group.end_date, 'Participants': [], 'Expenses': []} for group in groups}
    for person in await db.scalars(select(SplitBillParticipant).where(SplitBillParticipant.group_id.in_(ids)).order_by(SplitBillParticipant.position)):
        documents[person.group_id]['Participants'].append({'Id': person.id, 'Name': person.name})
    expenses = {}
    for expense in await db.scalars(select(SplitBillExpense).where(SplitBillExpense.group_id.in_(ids)).order_by(SplitBillExpense.position)):
        data = {'Id': expense.id, 'Name': expense.name, 'ExpenseDate': expense.expense_date, 'PaidBy': expense.paid_by,
                'ServiceCharge': {'Mode': expense.service_mode, 'Value': expense.service_value},
                'Tax': {'Mode': expense.tax_mode, 'Value': expense.tax_value}, 'TaxIncludesService': expense.tax_includes_service,
                'FeeAllocation': expense.fee_allocation, 'ReceiptTotal': expense.receipt_total, 'Notes': expense.notes, 'Items': []}
        expenses[(expense.group_id, expense.id)] = data
        documents[expense.group_id]['Expenses'].append(data)
    items = {}
    for item in await db.scalars(select(SplitBillItem).where(SplitBillItem.group_id.in_(ids)).order_by(SplitBillItem.position)):
        data = {'Id': item.id, 'Name': item.name, 'Amount': item.amount, 'SplitMode': item.split_mode, 'Shares': []}
        items[(item.group_id, item.expense_id, item.id)] = data
        expenses[(item.group_id, item.expense_id)]['Items'].append(data)
    for share in await db.scalars(select(SplitBillShare).where(SplitBillShare.group_id.in_(ids)).order_by(SplitBillShare.position)):
        items[(share.group_id, share.expense_id, share.item_id)]['Shares'].append({'ParticipantId': share.participant_id, 'Amount': share.amount})
    result = []
    for group in groups:
        payload = GroupCreate.model_validate(documents[group.id])
        result.append({'Id': str(group.id), 'Version': group.version, **payload.model_dump(mode='json', by_alias=True), 'Calculation': calculate(payload)})
    return result


async def response(item, db):
    return (await responses([item], db))[0]


async def owned(group_id, user_id, db, lock=False):
    query = select(SplitBillGroup).where(SplitBillGroup.id == group_id, SplitBillGroup.user_id == user_id)
    item = await db.scalar(query.with_for_update() if lock else query.with_for_update(read=True))
    if item is None:
        raise HTTPException(404, 'Split bill group not found')
    return item


async def delete_group(group_id, user_id, db):
    await db.delete(await owned(group_id, user_id, db, True))
    await db.commit()


async def list_groups(user_id, db):
    rows = await db.scalars(select(SplitBillGroup).where(SplitBillGroup.user_id == user_id).order_by(SplitBillGroup.created_at.desc(), SplitBillGroup.id).with_for_update(read=True))
    return await responses(list(rows), db)


async def save(payload, user_id, db, group_id=None):
    calculate(payload)
    if group_id is None:
        item = SplitBillGroup(user_id=user_id, version=1)
        db.add(item)
    else:
        item = await owned(group_id, user_id, db, True)
        if payload.version != item.version:
            raise HTTPException(409, 'Grup telah berubah. Muat ulang sebelum menyimpan.')
        item.version += 1
    item.name, item.start_date, item.end_date = payload.name, payload.start_date, payload.end_date
    await db.flush()
    # Full-group replacement is atomic and serialized by the existing group lock.
    for model in (SplitBillShare, SplitBillItem, SplitBillExpense, SplitBillParticipant):
        await db.execute(delete(model).where(model.group_id == item.id))
    participants, expenses, items, shares = [], [], [], []
    for position, person in enumerate(payload.participants):
        participants.append({'group_id': item.id, 'id': person.id, 'name': person.name, 'position': position})
    for position, expense in enumerate(payload.expenses):
        expenses.append({'group_id': item.id, 'id': expense.id, 'name': expense.name, 'expense_date': expense.expense_date,
                         'paid_by': expense.paid_by, 'service_mode': expense.service_charge.mode, 'service_value': expense.service_charge.value,
                         'tax_mode': expense.tax.mode, 'tax_value': expense.tax.value, 'tax_includes_service': expense.tax_includes_service,
                         'fee_allocation': expense.fee_allocation, 'receipt_total': expense.receipt_total, 'notes': expense.notes, 'position': position})
        for item_position, bill_item in enumerate(expense.items):
            items.append({'group_id': item.id, 'expense_id': expense.id, 'id': bill_item.id, 'name': bill_item.name,
                          'amount': bill_item.amount, 'split_mode': bill_item.split_mode, 'position': item_position})
            for share_position, share in enumerate(bill_item.shares):
                shares.append({'group_id': item.id, 'expense_id': expense.id, 'item_id': bill_item.id,
                               'participant_id': share.participant_id, 'amount': share.amount, 'position': share_position})
    for model, values in ((SplitBillParticipant, participants), (SplitBillExpense, expenses), (SplitBillItem, items), (SplitBillShare, shares)):
        if values:
            await db.execute(insert(model), values)
    result = await response(item, db)
    await db.commit()
    return result

