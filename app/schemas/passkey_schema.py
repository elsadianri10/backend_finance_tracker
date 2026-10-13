from typing import Any
from uuid import UUID
from pydantic import Field
from app.schemas.base_schema import PascalModel


class CredentialInput(PascalModel):
    challenge_id: UUID
    credential: dict[str, Any]
    name: str = Field(default='Passkey', min_length=1, max_length=80)


class RecoveryInput(PascalModel):
    code: str = Field(min_length=1, max_length=80)
