from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class StockNeed(Base):
    __tablename__ = 'stock_needs'
    __table_args__ = (
        CheckConstraint("category IN ('health','consumption','beauty')", name='ck_stock_category'),
        CheckConstraint("mode IN ('monthly','low_stock','manual')", name='ck_stock_mode'),
        CheckConstraint('reserve_threshold BETWEEN 0 AND 10000 AND version > 0', name='ck_stock_need_limits'),
        Index('ix_stock_need_owner', 'user_id'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(20))
    subcategory: Mapped[str] = mapped_column(String(60))
    mode: Mapped[str] = mapped_column(String(20))
    reserve_threshold: Mapped[int] = mapped_column(default=0)
    next_review: Mapped[date | None]
    snoozed_until: Mapped[date | None]
    paused: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)
    buy_requested: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(String(2000), default='')
    version: Mapped[int] = mapped_column(default=1)


class StockProduct(Base):
    __tablename__ = 'stock_products'
    __table_args__ = (
        CheckConstraint("preference IN ('staple','trial')", name='ck_stock_preference'),
        CheckConstraint('active_count BETWEEN 0 AND 10000 AND reserve_count BETWEEN 0 AND 10000 AND version > 0', name='ck_stock_counts'),
        Index('ix_stock_product_need', 'need_id'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    need_id: Mapped[UUID] = mapped_column(ForeignKey('stock_needs.id', ondelete='CASCADE'))
    brand: Mapped[str] = mapped_column(String(150))
    variant: Mapped[str] = mapped_column(String(150))
    package_unit: Mapped[str] = mapped_column(String(40))
    package_size: Mapped[str] = mapped_column(String(100))
    preference: Mapped[str] = mapped_column(String(10))
    active_count: Mapped[int] = mapped_column(default=0)
    reserve_count: Mapped[int] = mapped_column(default=0)
    near_empty: Mapped[bool] = mapped_column(default=False)
    opened_on: Mapped[date | None]
    archived: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)

    replenishment_paused: Mapped[bool] = mapped_column(default=False, server_default='false')
    replenishment_snoozed_until: Mapped[date | None]


class StockEvent(Base):
    __tablename__ = 'stock_events'
    __table_args__ = (
        UniqueConstraint('user_id', 'request_id', name='uq_stock_request'),
        CheckConstraint("kind IN ('purchase','open','finish','adjust')", name='ck_stock_event_kind'),
        CheckConstraint('quantity BETWEEN 0 AND 10000 AND (amount IS NULL OR amount BETWEEN 0 AND 1000000000000)', name='ck_stock_event_amount'),
        Index('ix_stock_event_product', 'product_id', 'event_date'),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    product_id: Mapped[UUID] = mapped_column(ForeignKey('stock_products.id', ondelete='CASCADE'))
    kind: Mapped[str] = mapped_column(String(10))
    event_date: Mapped[date]
    quantity: Mapped[int]
    active_delta: Mapped[int]
    reserve_delta: Mapped[int]
    brand: Mapped[str] = mapped_column(String(150))
    variant: Mapped[str] = mapped_column(String(150))
    amount: Mapped[int | None] = mapped_column(BigInteger)
    store: Mapped[str] = mapped_column(String(150), default='')
    notes: Mapped[str] = mapped_column(String(2000), default='')
    transaction_id: Mapped[UUID | None] = mapped_column(ForeignKey('ledger_transactions.id', ondelete='SET NULL'))
    request_id: Mapped[UUID]
    request_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
