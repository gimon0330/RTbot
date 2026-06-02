import traceback

import aiomysql
import discord
from discord.ext import commands


class DebugCommands(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content in {"!rawping", "알티야 rawping", "알티야rawping"}:
            await message.channel.send("raw message listener is working")
        if message.content in {"!dbcheck", "알티야 dbcheck", "알티야dbcheck"}:
            try:
                async with self.pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute("SELECT * FROM userdata WHERE id = %s", message.author.id)
                        user_rows = await cur.fetchall()
                        await cur.execute("SELECT COUNT(*) AS count FROM userdata")
                        count_row = await cur.fetchone()
                await message.channel.send(
                    f"db is working | userdata_count={count_row['count']} | your_rows={len(user_rows)}"
                )
            except Exception:
                await message.channel.send("dbcheck failed:\n```py\n" + traceback.format_exc()[-1500:] + "\n```")

    @commands.command(name="봇진단", aliases=["debugping"])
    async def debug_ping(self, ctx):
        await ctx.send("command parser is working")


async def setup(client):
    await client.add_cog(DebugCommands(client))
