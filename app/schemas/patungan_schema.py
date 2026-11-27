from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.base_schema import PascalModel

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
SupportedDate = Annotated[date, Field(ge=date(2000, 1, 1), le=date(2099, 12, 31))]


class SubscriptionInput(PascalModel):
    name: Name
    monthly_amount: int = Field(strict=True, ge=1, le=1_000_000_000)


class MemberInput(PascalModel):
    name: Name
    joined_on: SupportedDate
    left_on: SupportedDate | None = None
    pay_at_year_end: bool = False

    @model_validator(mode='after')
    def validate_dates(self):
        if self.left_on and self.left_on < self.joined_on:
            raise ValueError('Tanggal berhenti harus sama atau setelah tanggal masuk')
        return self


class MemberUpdate(MemberInput):
    version: int = Field(strict=True, ge=1)


class WaiverInput(PascalModel):
    month: SupportedDate
    waived: bool

    @field_validator('month')
    @classmethod
    def first_day(cls, value):
        if value.day != 1:
            raise ValueError('Pilih satu bulan')
        return value


class ReceiptInput(PascalModel):
    request_id: UUID
    transaction_id: UUID | None = None
    amount: int | None = Field(default=None, strict=True, ge=1, le=1_000_000_000_000)
    paid_on: SupportedDate | None = None
    start_month: SupportedDate | None = None
    notes: str = Field(default='', max_length=1000)

    @field_validator('start_month')
    @classmethod
    def first_day(cls, value):
        if value and value.day != 1:
            raise ValueError('Pilih bulan awal alokasi')
        return value

    @model_validator(mode='after')
    def payment_source(self):
        if self.transaction_id:
            if self.amount is not None or self.paid_on is not None:
                raise ValueError('Nominal dan tanggal mengikuti transaksi yang dipilih')
        elif self.amount is None or self.paid_on is None:
            raise ValueError('Isi nominal dan tanggal pembayaran')
        return self
