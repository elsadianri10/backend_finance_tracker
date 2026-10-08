from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base_schema import PascalModel, _to_pascal


class GoogleLoginRequest(PascalModel):
    id_token: str = Field(min_length=1, max_length=16384)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=_to_pascal, populate_by_name=True)
    id: UUID
    email: str
    name: str
    picture_url: str | None


class LoginResponse(PascalModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse
