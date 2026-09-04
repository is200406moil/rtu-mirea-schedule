import os

from dotenv import load_dotenv

load_dotenv(".env")


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEBUG = env_flag("DEBUG")
SECRET_REFRESH_KEY = os.getenv("SECRET_REFRESH_KEY")
REFRESH_LOCK_SECONDS = int(os.getenv("REFRESH_LOCK_SECONDS", 3600))
if REFRESH_LOCK_SECONDS < 60:
    raise RuntimeError("REFRESH_LOCK_SECONDS must be at least 60")

MAX_CONNECTIONS_COUNT = int(os.getenv("MAX_CONNECTIONS_COUNT", 10))
MIN_CONNECTIONS_COUNT = int(os.getenv("MIN_CONNECTIONS_COUNT", 10))

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://127.0.0.1:27017/")

API_V1_PREFIX = "/api"

DATABASE_NAME = "schedule"
SCHEDULE_COLLECTION_NAME = "schedule"
SESSION_COLLECTION_NAME = "session"
SCHEDULE_UPDATES_COLLECTION = "schedule_updates"
SCHEDULE_GROUPS_STATS = "schedule_groups_stats"
SCHEDULE_REFRESH_LOCKS = "schedule_refresh_locks"
SCHEDULE_REFRESH_STATUS = "schedule_refresh_status"
