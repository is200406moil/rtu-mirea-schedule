from pymongo import AsyncMongoClient

from ..core.config import MAX_CONNECTIONS_COUNT, MIN_CONNECTIONS_COUNT, MONGODB_URL
from .database import db


async def connect_to_mongo():
    db.client = AsyncMongoClient(
        MONGODB_URL,
        minPoolSize=MIN_CONNECTIONS_COUNT,
        maxPoolSize=MAX_CONNECTIONS_COUNT,
        tz_aware=True,
    )


async def close_mongo_connection():
    if db.client is not None:
        await db.client.close()
        db.client = None
