import discord
from discord.ext import commands


class DebugCommands(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.content in {"!rawping", "알티야 rawping", "알티야rawping"}:
            await message.channel.send("raw message listener is working")

    @commands.command(name="봇진단", aliases=["debugping"])
    async def debug_ping(self, ctx):
        await ctx.send("command parser is working")


async def setup(client):
    await client.add_cog(DebugCommands(client))
