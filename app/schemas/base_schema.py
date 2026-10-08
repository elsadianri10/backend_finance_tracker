from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _to_pascal(s: str) -> str:
    parts = s.split("_")
    return "".join(p[:1].upper() + p[1:] for p in parts if p)

class PascalModel(BaseModel):
    """Strict PascalCase request model.

    - Only accepts PascalCase keys (aliases).
    - Rejects snake_case / lowercase inputs.
    """

    model_config = ConfigDict(
        alias_generator=_to_pascal,
        populate_by_name=False,
        extra="forbid",
    )
