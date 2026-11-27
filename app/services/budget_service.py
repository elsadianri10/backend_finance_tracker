from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.budget_model import Budget, BudgetCategory, BudgetItem
from app.services.access_service import require_pro


def output(budget: Budget):
    categories = []
    for category in budget.categories:
        items = [
            {'Name': item.name, 'Brand': item.brand, 'Seller': item.seller,
             'Specification': item.specification, 'UnitPrice': item.unit_price,
             'Quantity': item.quantity, 'Link': item.link, 'Notes': item.notes,
             'Subtotal': item.unit_price * item.quantity}
            for item in category.items
        ]
        categories.append({'Name': category.name, 'Notes': category.notes, 'Items': items,
                           'Subtotal': sum(item['Subtotal'] for item in items)})
    return {'Id': budget.id, 'Version': budget.version, 'Name': budget.name, 'Months': budget.months,
            'Categories': categories, 'Total': sum(category['Subtotal'] for category in categories)}


def owned_query(user_id):
    return select(Budget).where(Budget.user_id == user_id).options(
        selectinload(Budget.categories).selectinload(BudgetCategory.items),
    )


async def list_budgets(user_id, db):
    await require_pro(user_id, db)
    budgets = await db.scalars(owned_query(user_id).order_by(Budget.name, Budget.id))
    return [output(budget) for budget in budgets]


async def locked_budget(budget_id, user_id, version, db):
    await require_pro(user_id, db)
    budget = await db.scalar(owned_query(user_id).where(Budget.id == budget_id)
                             .with_for_update().execution_options(populate_existing=True))
    if budget is None:
        raise HTTPException(404, 'Budget tidak ditemukan')
    if budget.version != version:
        raise HTTPException(409, 'Budget sudah berubah. Muat ulang sebelum melanjutkan.')
    return budget


async def save(payload, user_id, db, budget_id=None):
    if budget_id is None:
        await require_pro(user_id, db)
        budget = Budget(user_id=user_id, categories=[])
        db.add(budget)
    else:
        budget = await locked_budget(budget_id, user_id, payload.version, db)
        budget.version += 1
        budget.categories.clear()
        await db.flush()
    budget.name, budget.months = payload.name, payload.months
    for position, category in enumerate(payload.categories):
        items = [BudgetItem(position=index, **item.model_dump()) for index, item in enumerate(category.items)]
        budget.categories.append(BudgetCategory(position=position, name=category.name, notes=category.notes, items=items))
    await db.flush()
    result = output(budget)
    await db.commit()
    return result


async def delete(budget_id, user_id, version, db):
    budget = await locked_budget(budget_id, user_id, version, db)
    await db.delete(budget)
    await db.commit()
