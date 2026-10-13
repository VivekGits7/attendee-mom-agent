import json
from typing import Any, List, Optional

import asyncpg

from app.config import settings
from app.logger import get_logger

logger = get_logger(__name__)

_pool: Optional[asyncpg.Pool] = None


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def create_db_pool() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url, min_size=1, max_size=10, init=_init_connection
    )


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


async def execute_query(query: str, *args: Any) -> List[asyncpg.Record]:
    async with get_pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def execute_query_one(query: str, *args: Any) -> Optional[asyncpg.Record]:
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute_command(query: str, *args: Any) -> str:
    async with get_pool().acquire() as conn:
        return await conn.execute(query, *args)


async def execute_command_with_return(
    query: str, *args: Any
) -> Optional[asyncpg.Record]:
    async with get_pool().acquire() as conn:
        return await conn.fetchrow(query, *args)
