from pymongo import AsyncMongoClient


class DataBase:
    client: AsyncMongoClient | None = None


db = DataBase()


def get_database() -> AsyncMongoClient:
    if db.client is None:
        raise RuntimeError("MongoDB client is not initialized")
    return db.client
