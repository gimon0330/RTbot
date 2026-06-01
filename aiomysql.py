import re
from contextlib import asynccontextmanager

import asyncpg


class DictCursor:
    pass


def _normalize_args(args):
    if args is None:
        return []
    if isinstance(args, (list, tuple)):
        return list(args)
    return [args]


def _convert_placeholders(query):
    index = 0

    def replace(_match):
        nonlocal index
        index += 1
        return f"${index}"

    return re.sub(r"%s", replace, query)


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, query, args=None):
        params = _normalize_args(args)
        sql = _convert_placeholders(query)
        command = sql.lstrip().split(None, 1)[0].lower()

        if command in {"select", "show"}:
            records = await self.connection.fetch(sql, *params)
            self.rows = [dict(record) for record in records]
            return len(self.rows)

        result = await self.connection.execute(sql, *params)
        self.rows = []
        try:
            return int(result.rsplit(" ", 1)[-1])
        except (TypeError, ValueError):
            return 0

    async def fetchone(self):
        if not self.rows:
            return None
        return self.rows[0]

    async def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def cursor(self, *_args, **_kwargs):
        return Cursor(self.connection)


class Pool:
    def __init__(self, pool):
        self.pool = pool

    @asynccontextmanager
    async def acquire(self):
        async with self.pool.acquire() as connection:
            yield Connection(connection)

    async def close(self):
        await self.pool.close()


async def create_pool(
    *,
    url=None,
    host="localhost",
    port=5432,
    user=None,
    password=None,
    database=None,
    db=None,
    maxsize=20,
    ssl=None,
    **_kwargs,
):
    if url:
        pool = await asyncpg.create_pool(dsn=url, max_size=maxsize)
    else:
        pool = await asyncpg.create_pool(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database or db,
            max_size=maxsize,
            ssl=ssl,
        )
    return Pool(pool)
