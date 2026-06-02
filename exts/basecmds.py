import discord
from discord.ext import commands
from utils import errors, checks


def get_embed(title, description='', color=0xccffff):
    return discord.Embed(title=title, description=description, color=color)


class BaseCmds(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.master)

    @commands.group(name='ext', aliases=['확장'])
    async def _ext(self, ctx: commands.Context):
        pass

    @_ext.command(name='list', aliases=['목록'])
    async def _ext_list(self, ctx: commands.Context):
        allexts = ''
        for oneext in self.client.extensions:
            if oneext == self.__module__:
                allexts += f'🔐 {oneext}\n'
            else:
                allexts += f'✅ {oneext}\n'
        await ctx.send(embed=get_embed(f'🔌 전체 확장 목록', f"총 {len(self.client.extensions)}개의 확장\n{allexts}"))

    @commands.command(name='reload', aliases=['리'])
    async def _ext_reload(self, ctx: commands.Context, *names):
        reloads = self.client.extensions

        if (not names) or ('*' in names):
            for onename in list(reloads):
                await self.client.reload_extension(onename)
            await ctx.send(embed=get_embed("✅ 활성된 모든 확장을 리로드했습니다", "✅ " + "\n✅ ".join(reloads)))
        else:
            try:
                for onename in names:
                    if not (onename in reloads):
                        raise commands.ExtensionNotLoaded(f'로드되지 않은 확장: {onename}')
                for onename in names:
                    await self.client.reload_extension(onename)
            except commands.ExtensionNotLoaded:
                await ctx.send(f'**❓ 로드되지 않았거나 존재하지 않는 확장입니다: `{onename}`**')
            else:
                await ctx.send(f'**✅ 확장 리로드를 완료했습니다: `{", ".join(names)}`**')

    @commands.command(name='로드')
    async def extload(self, ctx, extension):
        try:
            await self.client.load_extension(f'exts.{extension}')
        except Exception:
            await ctx.send(f"LOAD\n<a:no:702745889751433277> {extension}")
        else:
            await ctx.send(f"LOAD\n<a:ok:702745889839775816> {extension}")

    @commands.command(name='언로드')
    async def extunload(self, ctx, extension):
        try:
            await self.client.unload_extension(f'exts.{extension}')
        except Exception:
            await ctx.send(f"UNLOAD\n<a:no:702745889751433277> {extension}")
        else:
            await ctx.send(f"UNLOAD\n<a:ok:702745889839775816> {extension}")


async def setup(client):
    await client.add_cog(BaseCmds(client))
