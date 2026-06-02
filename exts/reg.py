import discord, json, asyncio, aiomysql
from discord.ext import commands
from utils import errors, checks


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
        msg = await ctx.send(embed=get_embed("📝 | **알티봇 서비스에서 탈퇴하시겠습니까?**", "탈퇴시, 돈과 강화 목록을 포함한 모든 데이터가 영구적으로 삭제되며 복구할수 없습니다."))
        emjs = ['<a:yes:698461934198063104>', '<a:no:698461934613168199>']

        for em in emjs:
            await msg.add_reaction(em)

        def check(reaction, user):
            return user == ctx.author and msg.id == reaction.message.id and str(reaction.emoji) in emjs

        try:
            reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=20)
        except asyncio.TimeoutError:
            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('⏰ | 시간이 초과되었습니다!', "", 0xFF0000)),
            )
            return

        e = str(reaction.emoji)

        if e == '<a:yes:698461934198063104>':
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute('DELETE FROM userdata WHERE id = %s', ctx.author.id)

            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('<a:yes:698461934198063104> | 탈퇴에 성공했습니다!', "", 0xCCFFFF)),
            )
            return

        if e == '<a:no:698461934613168199>':
            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('<a:no:698461934613168199> | 취소 되었습니다!', "", 0xFF0000)),
            )
            return

    @commands.command(name='가입', aliases=['나도'])
    async def _login(self, ctx):
        msg = await ctx.send(embed=get_embed("📝 | **알티봇 서비스에 가입하시겠습니까?**", f"**NAME** = {ctx.author}\n**ID** = {ctx.author.id}"))
        emjs = ['<a:yes:698461934198063104>', '<a:no:698461934613168199>']

        for em in emjs:
            await msg.add_reaction(em)

        def check(reaction, user):
            return user == ctx.author and msg.id == reaction.message.id and str(reaction.emoji) in emjs

        try:
            reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=20)
        except asyncio.TimeoutError:
            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('⏰ | 시간이 초과되었습니다!', "", 0xFF0000)),
            )
            return

        e = str(reaction.emoji)

        if e == '<a:yes:698461934198063104>':
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        'INSERT INTO userdata VALUES(%s, %s, 0, 0, 0)',
                        (ctx.author.id, '5000'),
                    )

            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('<a:yes:698461934198063104> | 가입에 성공했습니다!', "", 0xCCFFFF)),
            )
            return

        if e == '<a:no:698461934613168199>':
            await asyncio.gather(
                msg.delete(),
                ctx.send(embed=get_embed('<a:no:698461934613168199> | 취소 되었습니다!', "", 0xFF0000)),
            )
            return


async def setup(client):
    await client.add_cog(reg(client))
