from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base_model import Base


class Wishlist(Base):
    __tablename__ = 'wishlists'
    __table_args__ = (CheckConstraint("kind IN ('things','consumables','games','food','holiday','vehicles','gadgets')", name='ck_wishlist_kind'),
        CheckConstraint("share_mode IN ('view','reserve')", name='ck_wishlist_share'), Index('ix_wishlist_owner', 'user_id'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(20))
    share_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    share_mode: Mapped[str] = mapped_column(String(10), default='view', server_default='view')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WishlistGroup(Base):
    __tablename__ = 'wishlist_groups'
    __table_args__ = (Index('ix_wishlist_group_list', 'wishlist_id'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    wishlist_id: Mapped[UUID] = mapped_column(ForeignKey('wishlists.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(150))


class WishlistItem(Base):
    __tablename__ = 'wishlist_items'
    __table_args__ = (CheckConstraint('price IS NULL OR price >= 0', name='ck_wishlist_price'),
        CheckConstraint("priority IN ('high','normal','low')", name='ck_wishlist_priority'),
        CheckConstraint("status IN ('wanted','sold_out','fulfilled','archived')", name='ck_wishlist_status'), Index('ix_wishlist_item_group', 'group_id'))
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    group_id: Mapped[UUID] = mapped_column(ForeignKey('wishlist_groups.id', ondelete='CASCADE'))
    name: Mapped[str] = mapped_column(String(300))
    platform: Mapped[str] = mapped_column(String(150), default='')
    brand: Mapped[str] = mapped_column(String(150), default='')
    model: Mapped[str] = mapped_column(String(200), default='')
    color: Mapped[str] = mapped_column(String(100), default='')
    capacity: Mapped[str] = mapped_column(String(100), default='')
    year: Mapped[str] = mapped_column(String(20), default='')
    plate: Mapped[str] = mapped_column(String(50), default='')
    country: Mapped[str] = mapped_column(String(100), default='')
    province: Mapped[str] = mapped_column(String(150), default='')
    city: Mapped[str] = mapped_column(String(150), default='')
    notes: Mapped[str] = mapped_column(Text, default='')
    link: Mapped[str] = mapped_column(String(2048), default='')
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 0))
    priority: Mapped[str] = mapped_column(String(10), default='normal', server_default='normal')
    status: Mapped[str] = mapped_column(String(12), default='wanted', server_default='wanted')


class WishlistPhoto(Base):
    __tablename__ = 'wishlist_photos'
    item_id: Mapped[UUID] = mapped_column(ForeignKey('wishlist_items.id', ondelete='CASCADE'), primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048))
    blob_url: Mapped[str | None] = mapped_column(String(2048))


class WishlistReservation(Base):
    __tablename__ = 'wishlist_reservations'
    item_id: Mapped[UUID] = mapped_column(ForeignKey('wishlist_items.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
