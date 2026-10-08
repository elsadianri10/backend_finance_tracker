from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator
from app.schemas.base_schema import PascalModel


class SavingCreate(PascalModel):
    kind: Literal['CASH', 'GOLD', 'DEPOSIT']
    metal_type: Literal['GOLD', 'SILVER'] | None = None
    name: str = Field(min_length=1, max_length=255)
    opening_amount: int | None = Field(default=None, strict=True, gt=0, le=1000000000000)
    start_date: date = Field(ge=date(2000, 1, 1))
    bank_account_id: UUID | None = None
    weight_per_piece: Decimal | None = Field(default=None, gt=0, le=100000, decimal_places=3)
    pieces: int | None = Field(default=None, strict=True, ge=1, le=10000)
    purchase_cost: int | None = Field(default=None, strict=True, ge=0, le=1000000000000)
    price_per_gram: int | None = Field(default=None, strict=True, gt=0, le=1000000000)
    maturity_date: date | None = None
    interest_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    notes: str = Field(default='', max_length=2000)

    @field_validator('name')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Nama simpanan wajib diisi')
        return value.strip()


class MovementCreate(PascalModel):
    request_id: UUID
    direction: Literal['ADD', 'REMOVE']
    amount: Decimal = Field(gt=0, le=1000000000000, decimal_places=3)
    movement_date: date
    notes: str = Field(default='', max_length=2000)


class MovementResponse(PascalModel):
    id: UUID
    sequence: int
    direction: str
    amount: float
    movement_date: date
    notes: str


class SavingResponse(PascalModel):
    id: UUID
    kind: str
    metal_type: str | None
    name: str
    opening_amount: float
    balance: float
    start_date: date
    bank_account_id: UUID | None
    bank_name: str | None
    bank_account_masked: str | None
    weight_per_piece: float | None
    pieces: int | None
    purchase_cost: int | None
    price_per_gram: int | None
    price_date: date | None
    estimated_value: int | None
    maturity_date: date | None
    interest_rate: float | None
    notes: str
    movements: list[MovementResponse]
