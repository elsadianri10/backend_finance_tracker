from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from app.schemas.base_schema import PascalModel

Category = Literal[
    'salary', 'food', 'transport', 'shopping', 'bills', 'health', 'other',
    'family', 'savings', 'top_up', 'entertainment', 'education', 'donation',
    'debt', 'bonus', 'investment', 'sales', 'receivable', 'cash_withdrawal',
]


class RoutineInput(PascalModel):
    kind: Literal['SUBSCRIPTION','CONTRIBUTION','TRANSFER']
    recipient: str = Field(default='', max_length=120)
    name: str = Field(min_length=1, max_length=200)
    amount: int = Field(strict=True, ge=0, le=1000000000000)
    status: Literal['ACTIVE','NOTE','STOPPED'] = 'ACTIVE'
    first_due_date: date = Field(ge=date(2000,1,1), le=date(2099,12,31))
    interval_months: int = Field(default=1, strict=True, ge=1, le=12)
    total_cycles: int = Field(default=0, strict=True, ge=0, le=60)
    initial_paid: int = Field(default=0, strict=True, ge=0, le=60)
    destination_bank_id: UUID | None = None
    billing_transaction_id: UUID | None = None
    debt_id: UUID | None = None
    saving_id: UUID | None = None
    notes: str = Field(default='', max_length=2000)

    @field_validator('name')
    @classmethod
    def required_name(cls, value):
        if not value.strip():
            raise ValueError('Nama wajib diisi')
        return value.strip()

    @model_validator(mode='after')
    def coherent(self):
        self.recipient = self.recipient.strip()
        if self.status == 'ACTIVE' and not self.amount:
            raise ValueError('Nominal aktif harus lebih dari 0 (nol)')
        if self.kind != 'SUBSCRIPTION' and not self.recipient:
            raise ValueError('Penerima wajib diisi')
        if self.total_cycles and self.initial_paid > self.total_cycles:
            raise ValueError('Pembayaran awal melebihi jumlah cicilan')
        if not self.total_cycles and self.initial_paid:
            raise ValueError('Progres awal hanya untuk cicilan terbatas')
        if self.kind == 'TRANSFER' and not self.destination_bank_id:
            raise ValueError('Pilih rekening tujuan milik sendiri')
        if self.kind != 'TRANSFER' and self.destination_bank_id:
            raise ValueError('Rekening tujuan hanya untuk alokasi tabungan')
        if self.kind == 'TRANSFER' and self.billing_transaction_id:
            raise ValueError('Transfer tidak dapat dihubungkan ke Tagihan')
        if self.debt_id and (self.kind != 'CONTRIBUTION' or self.billing_transaction_id):
            raise ValueError('Hubungan Hutang hanya untuk Setoran, pilih salah satu Hutang atau Tagihan')
        if self.saving_id and self.kind != 'TRANSFER':
            raise ValueError('Hubungan Savings hanya untuk Alokasi Tabungan')
        return self


class RoutineUpdate(RoutineInput):
    version: int = Field(strict=True, gt=0)


class PaymentInput(PascalModel):
    request_id: UUID
    sequence: int = Field(strict=True, gt=0)
    amount: int = Field(strict=True, gt=0, le=1000000000000)
    payment_date: date = Field(ge=date(2000,1,1), le=date(2099,12,31))
    source_bank_id: UUID | None = None
    billing_installment_id: UUID | None = None
    notes: str = Field(default='', max_length=2000)


class TransactionInput(PascalModel):
    request_id: UUID | None = None
    debt_id: UUID | None = None
    billing_installment_id: UUID | None = None
    routine_plan_id: UUID | None = None
    saving_id: UUID | None = None
    routine_sequence: int | None = Field(default=None, strict=True, gt=0)
    kind: Literal['income','expense','transfer']
    description: str = Field(min_length=1, max_length=200)
    category: Category = 'other'
    amount: int = Field(strict=True, gt=0, le=1000000000000)
    transaction_date: date = Field(ge=date(2000,1,1), le=date(2099,12,31))
    source_bank_id: UUID | None = None
    destination_bank_id: UUID | None = None
    notes: str = Field(default='', max_length=2000)

    @field_validator('description')
    @classmethod
    def required_description(cls, value):
        if not value.strip():
            raise ValueError('Keterangan wajib diisi')
        return value.strip()

    @model_validator(mode='after')
    def transfer_banks(self):
        if sum(bool(value) for value in (self.debt_id, self.billing_installment_id, self.routine_plan_id, self.saving_id)) > 1:
            raise ValueError('Pilih satu penghubung pembayaran')
        if any((self.debt_id, self.billing_installment_id, self.routine_plan_id, self.saving_id)) and not self.request_id:
            raise ValueError('RequestId wajib untuk pencatatan tertaut')
        if self.routine_plan_id and not self.routine_sequence:
            raise ValueError('Pilih pembayaran rutin berikutnya')
        if self.kind == 'transfer' and (not self.source_bank_id or not self.destination_bank_id or self.source_bank_id == self.destination_bank_id):
            raise ValueError('Transfer memerlukan dua rekening berbeda milik sendiri')
        if self.category == 'cash_withdrawal':
            if self.kind != 'income' or self.destination_bank_id:
                raise ValueError('Tarik Tunai menggunakan rekening sumber dan tujuan tunai')
        if self.kind == 'income' and self.category != 'cash_withdrawal' and self.source_bank_id or self.kind == 'expense' and self.destination_bank_id:
            raise ValueError('Rekening tidak sesuai jenis transaksi')
        return self


class LegacyTransaction(PascalModel):
    id: str = Field(min_length=1, max_length=200, alias='id')
    description: str = Field(min_length=1, max_length=200, alias='description')
    type: Literal['income','expense'] = Field(alias='type')
    category: Category = Field(alias='category')
    amount: int = Field(strict=True, gt=0, le=1000000000000, alias='amount')
    transaction_date: date = Field(ge=date(2000,1,1), le=date(2099,12,31), alias='date')


class ImportInput(PascalModel):
    transactions: list[LegacyTransaction] = Field(max_length=5000)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({row.id for row in self.transactions}) != len(self.transactions):
            raise ValueError('ID transaksi lama harus unik')
        return self
