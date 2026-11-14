from typing import Literal
from pydantic import AwareDatetime, ConfigDict, Field, model_validator
from app.schemas.base_schema import PascalModel


class AccessChange(PascalModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(strict=True, ge=0)
    action: Literal['GRANT', 'REVOKE']
    expires_at: AwareDatetime | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def coherent(self):
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError('Catatan perubahan wajib diisi')
        if self.action == 'REVOKE' and self.expires_at is not None:
            raise ValueError('Pencabutan akses tidak memakai tanggal berakhir')
        return self
