"""Postgres/pgvector access for the request pipeline (asyncpg pool + pgvector codec)."""
from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector


async def _init_connection(conn: asyncpg.Connection) -> None:
    await register_vector(conn)  # encode/decode vector(768) <-> Python list


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, init=_init_connection, min_size=1, max_size=5)
