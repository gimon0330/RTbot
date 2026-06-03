import os

from discord.ext import commands


def get_debug_enabled():
    return os.getenv("DEBUG_COMMAND_ERRORS", "false").lower() == "true"


class UxErrors(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if not get_debug_enabled():
            return
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(f"없는 명령어입니다: `{ctx.invoked_with}`\n`알티야 도움`으로 명령어 목록을 확인해보세요.")


async def setup(client):
    await client.add_cog(UxErrors(client))
