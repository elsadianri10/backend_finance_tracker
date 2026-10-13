from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.base_schema import PascalModel


class TransactionExportInput(PascalModel):
    month: str = Field(pattern=r'^20\d{2}-(0[1-9]|1[0-2])$')
    transaction_ids: list[UUID] = Field(min_length=1, max_length=5000)
    search: str = Field(default='', max_length=255)
    kind: Literal['all', 'income', 'expense', 'transfer'] = 'all'
    bank: str = Field(default='', max_length=255)

    @model_validator(mode='after')
    def unique_ids(self):
        if len(set(self.transaction_ids)) != len(self.transaction_ids):
            raise ValueError('Transaksi ekspor tidak boleh duplikat')
        return self
