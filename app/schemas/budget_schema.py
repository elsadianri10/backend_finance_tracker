from typing import Annotated

from pydantic import Field, HttpUrl, StringConstraints, TypeAdapter, field_validator, model_validator

from app.schemas.base_schema import PascalModel

TrimmedText = Annotated[str, StringConstraints(strip_whitespace=True)]
http_url = TypeAdapter(HttpUrl)


class BudgetItemInput(PascalModel):
    name: TrimmedText = Field(min_length=1, max_length=200)
    brand: TrimmedText = Field(default='', max_length=100)
    seller: TrimmedText = Field(default='', max_length=150)
    specification: TrimmedText = Field(default='', max_length=150)
    unit_price: int = Field(strict=True, ge=0, le=1000000000)
    quantity: int = Field(strict=True, ge=1, le=10000)
    link: TrimmedText = Field(default='', max_length=2048)
    notes: TrimmedText = Field(default='', max_length=1000)

    @field_validator('link')
    @classmethod
    def validate_link(cls, value: str) -> str:
        return str(http_url.validate_python(value)) if value else ''


class BudgetCategoryInput(PascalModel):
    name: TrimmedText = Field(min_length=1, max_length=100)
    notes: TrimmedText = Field(default='', max_length=1000)
    items: list[BudgetItemInput] = Field(default_factory=list, max_length=100)


class BudgetInput(PascalModel):
    name: TrimmedText = Field(min_length=1, max_length=150)
    months: int | None = Field(default=None, strict=True, ge=1, le=120)
    categories: list[BudgetCategoryInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def check_item_count(self):
        if sum(len(category.items) for category in self.categories) > 100:
            raise ValueError('Satu budget bisa memuat maksimal 100 item')
        return self


class BudgetUpdate(BudgetInput):
    version: int = Field(strict=True, gt=0)
