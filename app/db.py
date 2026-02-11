from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings


_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db():
    client = get_client()
    return client[settings.db_name]

