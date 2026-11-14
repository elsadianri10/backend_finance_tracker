from typing import Literal
from pydantic import ConfigDict, Field
from app.schemas.base_schema import PascalModel
class DeletionSubmit(PascalModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: str = Field(max_length=320)
class DeletionReview(PascalModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['REVIEW','PROCESS']
    confirmation: str = Field(default='',max_length=50)
