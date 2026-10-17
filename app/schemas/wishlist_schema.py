from typing import Literal
import re
from uuid import UUID
from urllib.parse import urlparse
from pydantic import Field, field_validator
from app.schemas.base_schema import PascalModel


class NamedInput(PascalModel):
    name: str = Field(min_length=1, max_length=300)

    @field_validator('name')
    @classmethod
    def meaningful_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Nama wajib diisi')
        return value.strip()


class WishlistInput(NamedInput):
    name: str = Field(min_length=1, max_length=150)
    kind: Literal['things', 'consumables', 'games', 'food', 'holiday', 'vehicles', 'gadgets']


class GroupInput(NamedInput):
    name: str = Field(min_length=1, max_length=150)


def valid_url(value: str) -> str:
    if value:
        parsed = urlparse(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Link harus berupa URL http atau https yang valid')
    return value


class ItemInput(NamedInput):
    group_id: UUID
    name: str = Field(min_length=1, max_length=300)
    platform: str = Field(default='', max_length=150)
    brand: str = Field(default='', max_length=150)
    model: str = Field(default='', max_length=200)
    color: str = Field(default='', max_length=100)
    capacity: str = Field(default='', max_length=100)
    year: str = Field(default='', max_length=20)
    plate: str = Field(default='', max_length=50)
    country: str = Field(default='', max_length=100)
    province: str = Field(default='', max_length=150)
    city: str = Field(default='', max_length=150)
    notes: str = Field(default='', max_length=3000)
    link: str = Field(default='', max_length=2048)
    price: int | None = Field(default=None, ge=0, le=999999999999999)
    priority: Literal['high', 'normal', 'low'] = 'normal'
    status: Literal['wanted', 'sold_out', 'fulfilled', 'archived'] = 'wanted'
    photos: list[str] = Field(default_factory=list, max_length=6)

    @field_validator('link')
    @classmethod
    def check_link(cls, value):
        return valid_url(value)

    @field_validator('photos')
    @classmethod
    def check_photos(cls, values):
        if any(not value or len(value) > 2048 for value in values):
            raise ValueError('URL foto tidak valid')
        return [value if re.fullmatch(r'/api/wishlists/images/[a-f0-9-]{36}/[0-5](?:\?v=[a-f0-9]{16})?', value) else valid_url(value) for value in values]
