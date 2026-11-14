from typing import Literal
from pydantic import ConfigDict,Field,field_validator
from app.schemas.base_schema import PascalModel
class AdminRoleChange(PascalModel):
    model_config=ConfigDict(extra='forbid')
    admin_f:int=Field(strict=True,ge=0,le=1)
    expected_admin_f:int=Field(strict=True,ge=0,le=1)
    reason:str=Field(min_length=1,max_length=500)
    @field_validator('reason')
    @classmethod
    def trim_reason(cls,value):
        if not value.strip():raise ValueError('Alasan wajib diisi')
        return value.strip()
