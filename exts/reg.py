import discord, json, asyncio, aiomysql
from discord.ext import commands
from utils import errors, checks
from utils.views import ask_confirm


def get_embed(title, description='', color=0xCCFFFF):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


class reg(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        self._logout.add_check(self.checks.registered)
        self._login.add_check(self.checks.already_registered)

    @commands.command(name='탈퇴')
    async def _logout(self, ctx):
        confirmed, msg = await ask_confirm(
            ctx,
            embed=get_embed("회원 탈퇴 확인", "탈퇴하면 돈과 강화 목록을 포함한 모든 데이터가 삭제됩니다."),
            timeout=30,
        )
        if confirmed is None:
            await ctx.send(embed=get_embed('시간이 초과되었습니다.', "", 0xFF0000))
            return
        if confirmed is False:
            await ctx.send(embed=get_embed('취소되었습니다.', "", 0xFF0000))
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('DELETE FROM reinforce WHERE id = %s', ctx.author.id)
                await cur.execute('DELETE FROM userdata WHERE id = %s', ctx.author.id)

        await ctx.send(embed=get_embed('탈퇴에 성공했습니다.', "", 0xCCFFFF))

    @commands.command(name='가입', aliases=['나도'])
    async def _login(self, ctx):
        confirmed, msg = await ask_confirm(
            ctx,
            embed=get_embed("회원 가입 확인", f"NAME = {ctx.author}\nID = {ctx.author.id}"),
            timeout=30,
        )
        if confirmed is None:
            await ctx.send(embed=get_embed('시간이 초과되었습니다.', "", 0xFF0000))
            return
        if confirmed is False:
            await ctx.send(embed=get_embed('취소되었습니다.', "", 0xFF0000))
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    'INSERT INTO userdata (id, money, bank, adminuser, blacklist) VALUES (%s, %s, %s, %s, %s)',
                    (ctx.author.id, '5000', '0', 0, 0),
                )

        await ctx.send(embed=get_embed('가입에 성공했습니다.', "", 0xCCFFFF))


async def setup(client):
    await client.add_cog(reg(client))
