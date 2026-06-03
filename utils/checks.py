import os

import aiomysql
from discord.ext import commands

from . import errors

OWNER_ID = int(os.getenv("OWNER_ID", "467666650183761920"))


class checks:
    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def fetch_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    'SELECT id, money, bank, adminuser, blacklist FROM userdata WHERE id = %s',
                    user_id,
                )
                return await cur.fetchone()

    async def money0up(self, ctx):
        user = await self.fetch_user(ctx.author.id)
        if user is None:
            raise errors.NotRegistered
        if int(user["money"]) >= 0:
            return True
        raise errors.NoMoney

    async def blacklist(self, ctx: commands.Context):
        user = await self.fetch_user(ctx.author.id)
        if user is None:
            return True
        if int(user["blacklist"]) == 0:
            return True
        raise errors.blacklistuser

    async def master(self, ctx: commands.Context):
        if ctx.author.id == OWNER_ID:
            return True

        user = await self.fetch_user(ctx.author.id)
        if user is not None and int(user["adminuser"]) == 1:
            return True
        raise errors.NotMaster

    async def registered(self, ctx: commands.Context):
        if await self.fetch_user(ctx.author.id) is not None:
            return True
        raise errors.NotRegistered

    async def already_registered(self, ctx):
        if await self.fetch_user(ctx.author.id) is None:
            return True
        raise errors.AlreadyRegistered
