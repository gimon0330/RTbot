import datetime
import io
import json

import aiomysql
import discord
from discord.ext import commands

from utils import checks, errors


with open("./data/noticechannel.json", "r", encoding="UTF8") as db_json:
    noticedb = json.load(db_json)


def get_embed(title, description="", color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


class admincmds(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.master)

    async def sendlog(self, ctx):
        channel = self.client.get_channel(784252753806491658)

        if channel is None:
            return

        await channel.send(
            f"name: **{ctx.author.name}** id: **{ctx.author.id}**\n"
            f"content: ```py\n{ctx.message.content}```\n"
            f"datetime: `{datetime.datetime.now()}`"
        )

    @commands.command(name="강화설정")
    async def reinforce_set(self, ctx, uid: int, name: str, level: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "UPDATE reinforce SET level = %s WHERE id = %s AND name = %s",
                    (level, uid, name),
                )

        await self.sendlog(ctx)

    @commands.command(name="돈설정")
    async def _money_set(self, ctx, uid, n: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "UPDATE userdata SET money = %s WHERE id = %s",
                    (str(n), uid),
                )

        await ctx.send(f"SETTED money\nuid: {uid}\nn: {n}")
        await self.sendlog(ctx)

    @commands.command(name="은행설정")
    async def _bank_set(self, ctx, uid, n: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "UPDATE userdata SET bank = %s WHERE id = %s",
                    (str(n), uid),
                )

        await ctx.send(f"SETTED bank\nuid: {uid}\nn: {n}")
        await self.sendlog(ctx)

    @commands.command(name="강제가입")
    async def _force_register(self, ctx: commands.Context, uid):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if await cur.execute("SELECT * FROM userdata WHERE id = %s", uid) != 0:
                    await ctx.send("Already Registered")
                    return

                await cur.execute(
                    "INSERT INTO userdata VALUES(%s, %s, 0, 0, 0)",
                    (uid, "5000"),
                )

        await ctx.send(f"Setted\nuid: {uid}")
        await self.sendlog(ctx)

    @commands.command(name="유저등록확인")
    async def _check_user_existing(self, ctx: commands.Context, uid):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.sendlog(ctx)

                if await cur.execute("SELECT * FROM userdata WHERE id = %s", uid) != 0:
                    await cur.execute("SELECT * FROM userdata WHERE id = %s", uid)
                    fetch = await cur.fetchall()
                    await ctx.send(f"Registered USER : {uid}\n{fetch}")
                    return

                await ctx.send("Not registered")

    @commands.command(name="어드민추가")
    async def _add_admin(self, ctx: commands.Context, uid):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.sendlog(ctx)

                if await cur.execute("SELECT * FROM userdata WHERE id = %s", uid) == 0:
                    await cur.execute(
                        "INSERT INTO userdata VALUES(%s, %s, 0, 1, 0)",
                        (uid, "5000"),
                    )
                    await ctx.send("Done. + force registered")
                    return

                await cur.execute(
                    "UPDATE userdata SET adminuser = 1 WHERE id = %s",
                    uid,
                )

        await ctx.send("Done.")

    @commands.command(name="블랙추가")
    async def _up_black(self, ctx, uid):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.sendlog(ctx)

                if await cur.execute("SELECT * FROM userdata WHERE id = %s", uid) == 0:
                    await cur.execute(
                        "INSERT INTO userdata VALUES(%s, %s, 0, 0, 1)",
                        (uid, "5000"),
                    )
                    await ctx.send("Done. + force registered")
                    return

                await cur.execute(
                    "UPDATE userdata SET blacklist = 1 WHERE id = %s",
                    uid,
                )

        await ctx.send("Done.")

    @commands.command(name="블랙제거")
    async def _down_black(self, ctx, uid):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.sendlog(ctx)

                if await cur.execute("SELECT * FROM userdata WHERE id = %s", uid) == 0:
                    await ctx.send("Not Registered")
                    return

                await cur.execute(
                    "UPDATE userdata SET blacklist = 0 WHERE id = %s",
                    uid,
                )

        await ctx.send("Done.")

    @commands.command(name="공지보내")
    async def _notice_send(self, ctx, *, arg):
        if ctx.author.id != 467666650183761920:
            raise errors.NotMaster

        success_list = ["SUCCEED LIST"]
        fail_list = ["FAIL LIST"]

        send_control_panel = await ctx.send(embed=get_embed("공지 전송중", ""))

        for guild in self.client.guilds:
            sent_server = guild.name
            selected_channel = None
            fallback_channel = None

            if str(guild.id) in noticedb:
                selected_channel = self.client.get_channel(noticedb[str(guild.id)])
            else:
                for channel in guild.text_channels:
                    if not channel.permissions_for(guild.me).send_messages:
                        continue

                    if fallback_channel is None:
                        fallback_channel = channel

                    lower_name = channel.name.lower()

                    if "공지" in channel.name and "봇" in channel.name:
                        selected_channel = channel
                        break
                    if "noti" in lower_name and "bot" in lower_name:
                        selected_channel = channel
                        break
                    if "공지" in channel.name:
                        selected_channel = channel
                        break
                    if "noti" in lower_name:
                        selected_channel = channel
                        break
                    if "봇" in channel.name:
                        selected_channel = channel
                        break
                    if "bot" in lower_name:
                        selected_channel = channel
                        break

                if selected_channel is None:
                    selected_channel = fallback_channel

            try:
                if selected_channel is None:
                    raise RuntimeError("No writable channel found")

                await selected_channel.send(
                    embed=get_embed(
                        "<a:waiting:712170404869046334> ｜ 알티봇 공지",
                        arg
                        + "\n\n모든 문의,건의는 [알티봇 서포트](https://discord.gg/hTZxtbC) 에서 해주세요."
                        + "\n[알티봇 초대하기](https://discordapp.com/api/oauth2/authorize?client_id=661477460390707201&permissions=8&scope=bot) ",
                    )
                )
                success_list.append("성공 " + sent_server)
            except Exception:
                fail_list.append("실패 " + sent_server)

            await send_control_panel.edit(
                embed=get_embed(
                    "공지 전송중",
                    f"성공 : {len(success_list) - 1}\n실패 : {len(fail_list) - 1}",
                )
            )

        await ctx.send("성공")

        logfile = discord.File(
            fp=io.StringIO("\n".join(success_list) + "\n\n" + "\n".join(fail_list)),
            filename="notilog.log",
        )
        await ctx.send(file=logfile)


async def setup(client):
    await client.add_cog(admincmds(client))
