from pathlib import Path
from zoneinfo import ZoneInfo

# APP CONFIG
APP_NAME = "app"
APP_TZ_NAME = 'Asia/Jakarta'
APP_TZ = ZoneInfo(APP_TZ_NAME)

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = (BASE_DIR / "logs").resolve()
