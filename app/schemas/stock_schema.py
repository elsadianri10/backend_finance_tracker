from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from app.schemas.base_schema import PascalModel

SUBCATEGORIES = {
    'health': ('vitamins', 'medicines', 'other_health'),
    'consumption': ('food', 'drinks', 'other_consumption'),
    'beauty': ('skincare', 'oral_care', 'body_care', 'hair_care', 'makeup', 'other_beauty'),
}


class NeedInput(PascalModel):
    name: str = Field(min_length=1, max_length=150)
    category: Literal['health', 'consumption', 'beauty']
    subcategory: str = Field(max_length=60)
    mode: Literal['monthly', 'low_stock', 'manual'] = 'low_stock'
    reserve_threshold: int = Field(default=0, strict=True, ge=0, le=10000)
    next_review: date | None = Field(default=None, ge=date(2000, 1, 1), le=date(2098, 12, 31))
    notes: str = Field(default='', max_length=2000)
    version: int = Field(default=0, strict=True, ge=0)

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Nama wajib diisi')
        return value.strip()

    @model_validator(mode='after')
    def category_and_schedule(self):
        if self.subcategory not in SUBCATEGORIES[self.category]:
            raise ValueError('Subkategori tidak sesuai kategori')
        if self.mode == 'monthly' and not self.next_review:
            raise ValueError('Tanggal pengingat bulanan wajib diisi')
        if self.mode != 'monthly':
            self.next_review = None
        return self


class ProductInput(PascalModel):
    request_id: UUID
    version: int = Field(default=0, strict=True, ge=0)
    brand: str = Field(default='', max_length=150)
    variant: str = Field(default='', max_length=150)
    package_unit: str = Field(default='kemasan', min_length=1, max_length=40)
    package_size: str = Field(default='', max_length=100)
    preference: Literal['staple', 'trial'] = 'staple'
    active_count: int = Field(default=0, strict=True, ge=0, le=10000)
    reserve_count: int = Field(default=0, strict=True, ge=0, le=10000)
    near_empty: bool = False
    opened_on: date | None = Field(default=None, ge=date(2000, 1, 1), le=date(2099, 12, 31))
    archived: bool = False

    @field_validator('package_unit')
    @classmethod
    def unit_not_blank(cls, value):
        if not value.strip():
            raise ValueError('Satuan wajib diisi')
        return value.strip()

    @model_validator(mode='after')
    def counts(self):
        if self.archived and (self.active_count or self.reserve_count):
            raise ValueError('Habiskan atau sesuaikan stok sebelum mengarsipkan produk')
        if not self.active_count:
            self.near_empty = False
            self.opened_on = None
        return self


class NeedAction(PascalModel):
    version: int = Field(strict=True, gt=0)
    action: Literal['pause', 'resume', 'skip', 'request', 'cancel_request', 'archive', 'restore']


class ProductAction(PascalModel):
    request_id: UUID
    version: int = Field(strict=True, gt=0)
    action: Literal['open', 'finish', 'near_empty', 'not_near_empty']
    event_date: date = Field(ge=date(2000, 1, 1), le=date(2099, 12, 31))
    open_next: bool = True


class PurchaseInput(PascalModel):
    request_id: UUID
    version: int = Field(strict=True, gt=0)
    quantity: int = Field(strict=True, gt=0, le=10000)
    purchase_date: date = Field(ge=date(2000, 1, 1), le=date(2098, 12, 31))
    amount: int | None = Field(default=None, strict=True, ge=0, le=1000000000000)
    store: str = Field(default='', max_length=150)
    notes: str = Field(default='', max_length=2000)
    record_expense: bool = False
    source_bank_id: UUID | None = None

    @model_validator(mode='after')
    def expense(self):
        if self.record_expense and not self.amount:
            raise ValueError('Nominal pengeluaran harus lebih dari nol')
        if self.source_bank_id and not self.record_expense:
            raise ValueError('Rekening hanya untuk pencatatan pengeluaran')
        return self
