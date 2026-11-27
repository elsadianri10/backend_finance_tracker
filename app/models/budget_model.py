from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base_model import Base


class Budget(Base):
    __tablename__ = 'budgets'
    __table_args__ = (
        Index('ix_budgets_user_id', 'user_id'),
        CheckConstraint('months BETWEEN 1 AND 120', name='ck_budget_months'),
        CheckConstraint('version > 0', name='ck_budget_version'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))
    months: Mapped[int | None]
    version: Mapped[int] = mapped_column(default=1, server_default='1')
    categories: Mapped[list['BudgetCategory']] = relationship(
        order_by='BudgetCategory.position', cascade='all, delete-orphan', passive_deletes=True,
    )


class BudgetCategory(Base):
    __tablename__ = 'budget_categories'
    __table_args__ = (UniqueConstraint('budget_id', 'position', name='uq_budget_category_position'),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    budget_id: Mapped[UUID] = mapped_column(ForeignKey('budgets.id', ondelete='CASCADE'))
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(String(1000))
    items: Mapped[list['BudgetItem']] = relationship(
        order_by='BudgetItem.position', cascade='all, delete-orphan', passive_deletes=True,
    )


class BudgetItem(Base):
    __tablename__ = 'budget_items'
    __table_args__ = (
        UniqueConstraint('category_id', 'position', name='uq_budget_item_position'),
        CheckConstraint('quantity BETWEEN 1 AND 10000', name='ck_budget_item_quantity'),
        CheckConstraint('unit_price BETWEEN 0 AND 1000000000', name='ck_budget_item_price'),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    category_id: Mapped[UUID] = mapped_column(ForeignKey('budget_categories.id', ondelete='CASCADE'))
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str] = mapped_column(String(100))
    seller: Mapped[str] = mapped_column(String(150))
    specification: Mapped[str] = mapped_column(String(150))
    unit_price: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int]
    link: Mapped[str] = mapped_column(String(2048))
    notes: Mapped[str] = mapped_column(String(1000))
