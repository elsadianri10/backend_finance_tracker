from uuid import UUID
from pydantic import Field
from app.schemas.base_schema import PascalModel


class BankAccountCreate(PascalModel):
    platform_id: int = Field(strict=True, gt=0)
    account_number: str = Field(pattern=r"^[0-9]{5,30}$")
    card_number: str = Field(pattern=r"^[0-9]{12,19}$")
    valid_thru: str = Field(pattern=r"^20[0-9]{2}-(0[1-9]|1[0-2])$")
    admin_fee: int = Field(default=0, strict=True, ge=0, le=1000000000000)
    others_fee: int = Field(default=0, strict=True, ge=0, le=1000000000000)


class BankAccountUpdate(BankAccountCreate):
    # Omitted values preserve the encrypted numbers; null/empty is invalid.
    account_number: str = Field(default=None, pattern=r"^[0-9]{5,30}$")
    card_number: str = Field(default=None, pattern=r"^[0-9]{12,19}$")


class BankAccountResponse(PascalModel):
    id: UUID
    platform_id: int
    platform_name: str
    account_number_masked: str
    card_number_masked: str
    valid_thru: str
    admin_fee: int
    others_fee: int


class WalletProviderResponse(PascalModel):
    id: int
    name: str
    bank_f: int
