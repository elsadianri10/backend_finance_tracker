import os
from fastapi import HTTPException

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
TOKEN_ISSUER = "finance-tracker"
TOKEN_AUDIENCE = "finance-tracker-api"


def require_token_settings():
    if (
        len(SECRET_KEY.encode()) < 32
        or SECRET_KEY in {
            "SANGAT_PANJANG_RANDOM_SECRET_PROD_JANGAN_DISEBAR",
            "replace-with-a-random-secret-at-least-32-bytes",
        }
        or ACCESS_TOKEN_EXPIRE_MINUTES <= 0
    ):
        raise HTTPException(503, "Configure a random SECRET_KEY and a positive token lifetime")
