from datetime import date, datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from app.schemas.base_schema import PascalModel


class TransactionCreate(PascalModel):
    description: str = Field(min_length=1, max_length=255)
    tenor: Literal[0, 3, 6, 9, 12, 18, 24] = 0
    transaction_kind: Literal['ONE_TIME', 'INSTALLMENT', 'SUBSCRIPTION'] | None = None
    transaction_date: date | None = Field(default=None, ge=date(2000, 1, 1), le=date(9997, 12, 31))
    first_installment: date | None = Field(default=None, le=date(9997, 12, 31))
    last_installment: date | None = None
    amount: int = Field(strict=True, gt=0, le=9007199254740991)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def kind_fields(self):
        if self.transaction_kind is None:
            self.transaction_kind = 'INSTALLMENT' if self.tenor else 'ONE_TIME'
        if self.transaction_date is None and self.first_installment is None:
            raise ValueError('TransactionDate is required')
        if self.transaction_kind == 'SUBSCRIPTION':
            if self.tenor != 0 or self.last_installment is not None:
                raise ValueError('Subscription must not contain tenor or last installment date')
            if self.first_installment is not None and self.first_installment < date(2000, 1, 1):
                raise ValueError('Subscription start must be on or after 2000-01-01')
        elif (self.transaction_date is None and self.last_installment is None) or (self.transaction_kind == 'INSTALLMENT') != (self.tenor > 0):
            raise ValueError('Transaction kind, tenor and last installment date must match')
        return self

    @field_validator("description")
    @classmethod
    def non_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Description is required")
        return value

    @field_validator("tenor", mode="before")
    @classmethod
    def integer_tenor(cls, value):
        if type(value) is not int:
            raise ValueError("Tenor must be an integer")
        return value


class LastAmountUpdate(PascalModel):
    amount: int = Field(strict=True, gt=0, le=9007199254740991)


class InstallmentResponse(PascalModel):
    id: UUID
    sequence: int
    amount: int
    due_date: date
    paid_at: datetime | None
    charged_on: date | None = None


class TransactionResponse(PascalModel):
    transaction_date: date | None
    id: UUID
    account_id: UUID
    description: str
    tenor: int
    first_installment: date
    last_installment: date | None
    transaction_kind: Literal['ONE_TIME', 'INSTALLMENT', 'SUBSCRIPTION']
    stopped_on: date | None
    next_charge_date: date | None
    next_due_date: date | None
    amount: int
    notes: str
    installments: list[InstallmentResponse]
