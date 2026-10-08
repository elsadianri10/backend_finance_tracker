from datetime import date
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import Field, StrictInt, field_validator
from app.schemas.base_schema import PascalModel


class DebtKind(str, Enum):
    DEBT = "DEBT"
    RECEIVABLE = "RECEIVABLE"


class InterestType(str, Enum):
    NONE = "NONE"
    MONTHLY = "MONTHLY"


class DebtCreate(PascalModel):
    kind: DebtKind
    person_name: str = Field(min_length=1, max_length=255)
    principal: int = Field(strict=True, gt=0, le=1000000000000)
    transaction_date: date = Field(ge=date(2000, 1, 1))
    due_date: date | None = None
    source_bank_account_id: UUID | None = None
    installment_count: int = Field(default=0, strict=True, ge=0, le=60)
    installment_amounts: list[StrictInt] | None = Field(default=None, max_length=60)
    interest_type: InterestType = InterestType.NONE
    interest_rate: Decimal = Field(default=Decimal(0), ge=0, le=100, decimal_places=2)
    notes: str = Field(default="", max_length=2000)

    @field_validator("person_name")
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError("Nama orang wajib diisi")
        return value.strip()


class PaymentCreate(PascalModel):
    request_id: UUID
    amount: int = Field(strict=True, gt=0, le=9007199254740991)
    payment_date: date
    notes: str = Field(default="", max_length=2000)


class PaymentResponse(PascalModel):
    id: UUID
    sequence: int
    amount: int
    payment_date: date
    notes: str
    interest_portion: int
    principal_portion: int


class InterestChargeResponse(PascalModel):
    date: date
    principal_base: int
    amount: int


class InstallmentResponse(PascalModel):
    sequence: int
    due_date: date
    principal_amount: int
    paid_principal: int
    remaining_principal: int
    is_paid: bool


class InstallmentsUpdate(PascalModel):
    amounts: list[StrictInt] = Field(min_length=1, max_length=60)


class DebtResponse(PascalModel):
    id: UUID
    kind: DebtKind
    person_name: str
    principal: int
    transaction_date: date
    due_date: date | None
    source_bank_account_id: UUID | None
    source_bank_name: str | None
    source_account_number_masked: str | None
    installment_count: int
    installments: list[InstallmentResponse]
    interest_type: InterestType
    interest_rate: float
    notes: str
    interest_accrued: int
    total_amount: int
    paid_amount: int
    remaining_principal: int
    remaining_interest: int
    remaining_amount: int
    is_settled: bool
    is_history_visible: bool
    is_overdue: bool
    can_delete: bool
    next_interest_date: date | None
    payments: list[PaymentResponse]
    interest_charges: list[InterestChargeResponse]
