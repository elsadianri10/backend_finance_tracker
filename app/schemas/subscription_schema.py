from typing import Literal
from uuid import UUID
from pydantic import ConfigDict, Field, model_validator
from app.schemas.base_schema import PascalModel


class SubscriptionCheckout(PascalModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    plan: Literal['MONTHLY', 'ANNUAL']
    auto_renew: bool = Field(strict=True)
    expected_amount: int | None = Field(default=None, strict=True, ge=1, le=10000000)
    consent_version: Literal['2026-11-02'] | None = None

    @model_validator(mode='after')
    def consent(self):
        if self.auto_renew and self.consent_version is None:
            raise ValueError('Persetujuan autodebit diperlukan')
        return self
