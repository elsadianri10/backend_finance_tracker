from enum import Enum
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from app.schemas.base_schema import PascalModel


class PlatformType(str, Enum):
    CREDIT_CARD = "CREDIT_CARD"
    PAY_LATER = "PAY_LATER"


class BillingAccountCreate(PascalModel):
    platform_id: int = Field(strict=True, gt=0)
    platform_type: PlatformType
    account_type: str | None = Field(default=None, min_length=1, max_length=100)
    # A string preserves leading zeroes and avoids browser number precision loss.
    account_number: str | None = Field(default=None, pattern=r"^[0-9]{12,19}$")
    valid_thru: str | None = Field(default=None, pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
    has_fixed_bill_date: StrictBool
    billing_date: int | None = Field(default=None, strict=True, ge=1, le=31)
    due_date: int | None = Field(default=None, strict=True, ge=1, le=31)

    @model_validator(mode="after")
    def validate_conditional_fields(self):
        if self.platform_type == PlatformType.CREDIT_CARD:
            if not self.account_type or not self.account_type.strip() or self.account_number is None or self.valid_thru is None:
                raise ValueError("Credit Card requires AccountType, AccountNumber and ValidThru")
            self.account_type = self.account_type.strip()
        elif any(x is not None for x in (self.account_type, self.account_number, self.valid_thru)):
            raise ValueError("Pay Later must not contain credit card fields")
        if self.has_fixed_bill_date:
            if self.billing_date is None or self.due_date is None:
                raise ValueError("Fixed billing requires BillingDate and DueDate")
        elif self.billing_date is not None or self.due_date is not None:
            raise ValueError("Non-fixed billing must not contain BillingDate or DueDate")
        return self


class BillingPlatformResponse(PascalModel):
    id: int
    name: str
    bank_f: int
    supported_types: list[PlatformType]


class BillingAccountUpdate(BillingAccountCreate):
    @model_validator(mode="after")
    def validate_conditional_fields(self):
        if self.platform_type == PlatformType.CREDIT_CARD:
            if not self.account_type or not self.account_type.strip() or self.valid_thru is None:
                raise ValueError("Credit Card requires AccountType and ValidThru")
            self.account_type = self.account_type.strip()
        elif any(x is not None for x in (self.account_type, self.account_number, self.valid_thru)):
            raise ValueError("Pay Later must not contain credit card fields")
        if self.has_fixed_bill_date:
            if self.billing_date is None or self.due_date is None:
                raise ValueError("Fixed billing requires BillingDate and DueDate")
        elif self.billing_date is not None or self.due_date is not None:
            raise ValueError("Non-fixed billing must not contain BillingDate or DueDate")
        return self


class BillingAccountResponse(PascalModel):
    id: UUID
    platform_id: int
    platform_name: str
    platform_type: PlatformType
    account_type: str | None
    account_number_masked: str | None
    valid_thru: str | None
    has_fixed_bill_date: bool
    billing_date: int | None
    due_date: int | None
    has_transactions: bool
    can_delete: bool
