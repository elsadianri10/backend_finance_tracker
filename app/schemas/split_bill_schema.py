from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictBool, field_validator, model_validator
from app.schemas.base_schema import PascalModel


class Participant(PascalModel):
    id: UUID
    name: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def name_required(cls, value):
        if not value.strip():
            raise ValueError('Nama peserta wajib diisi')
        return value.strip()


class ItemShare(PascalModel):
    participant_id: UUID
    amount: int = Field(strict=True, ge=0, le=1000000000000)


class BillItem(PascalModel):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    amount: int = Field(strict=True, gt=0, le=1000000000000)
    split_mode: Literal['EQUAL', 'CUSTOM'] = 'EQUAL'
    shares: list[ItemShare] = Field(min_length=1, max_length=20)

    @field_validator('name')
    @classmethod
    def item_required(cls, value):
        if not value.strip():
            raise ValueError('Keterangan item wajib diisi')
        return value.strip()


class Charge(PascalModel):
    mode: Literal['AMOUNT', 'PERCENT'] = 'AMOUNT'
    value: Decimal = Field(default=Decimal(0), ge=0, le=1000000000000, decimal_places=2)

    @model_validator(mode='after')
    def valid_charge(self):
        if self.mode == 'PERCENT' and self.value > 100:
            raise ValueError('Persentase maksimal 100%')
        if self.mode == 'AMOUNT' and self.value != self.value.to_integral_value():
            raise ValueError('Nominal rupiah harus bulat')
        return self


class Expense(PascalModel):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    expense_date: date
    paid_by: UUID
    items: list[BillItem] = Field(min_length=1, max_length=100)
    service_charge: Charge = Field(default_factory=lambda: Charge())
    tax: Charge = Field(default_factory=lambda: Charge())
    tax_includes_service: StrictBool = True
    fee_allocation: Literal['PROPORTIONAL', 'EQUAL', 'MIXED'] = 'MIXED'
    receipt_total: int | None = Field(default=None, strict=True, ge=0, le=1000000000000)
    notes: str = Field(default='', max_length=2000)

    @field_validator('name')
    @classmethod
    def expense_required(cls, value):
        if not value.strip():
            raise ValueError('Nama pengeluaran wajib diisi')
        return value.strip()


class GroupCreate(PascalModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: date = Field(ge=date(2000, 1, 1))
    end_date: date
    participants: list[Participant] = Field(min_length=2, max_length=20)
    expenses: list[Expense] = Field(default_factory=list, max_length=100)

    @field_validator('name')
    @classmethod
    def group_required(cls, value):
        if not value.strip():
            raise ValueError('Nama grup wajib diisi')
        return value.strip()


class GroupUpdate(GroupCreate):
    version: int = Field(strict=True, gt=0)

