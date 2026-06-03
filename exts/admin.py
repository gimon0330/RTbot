import asyncio
import datetime
import io
import json
import os
import uuid

import aiomysql
import discord
from discord.ext import commands

from utils import checks, errors
from utils.shop_items import SHOP_ITEMS, format_money, get_item, resolve_item_key
from utils.views import ask_confirm

ADMIN_LOG_CHANNEL_ID = int(os.getenv("ADMIN_LOG_CHANNEL_ID", "784252753806491658"))
NOTICE_CHANNEL_FILE = "./data/noticechannel.json"
MIN_ITEM_NAME_LENGTH = 2
MAX_ITEM_NAME_LENGTH = 15
BLOCKED_STAR_EMOJIS = {'⭐', '🌟', '✨', '💫', '🌠', '✴️', '✳️', '❇️', '✡️'}


def load_notice_channels():
    try:
        with open(NOTICE_CHANNEL_FILE, "r", encoding="UTF8") as db_json:
            return json.load(db_json)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


noticedb = load_notice_channels()


def get_embed(title, description="", color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


def validate_item_name(name: str):
    stripped = name.strip()
    if len(stripped) < MIN_ITEM_NAME_LENGTH or len(stripped) > MAX_ITEM_NAME_LENGTH:
        return False, f"아이템 이름은 {MIN_ITEM_NAME_LENGTH}글자 이상 {MAX_ITEM_NAME_LENGTH}자 이내여야 합니다."
    if any(star in stripped for star in BLOCKED_STAR_EMOJIS):
        return False, "아이템 이름에는 별 이모지를 사용할 수 없습니다."
    return True, stripped


def star_count(level: int) -> int:
    return max(0, level - 100)


def star_icons(stars: int) -> str:
    if stars <= 0:
        return ""
    big_stars, small_stars = divmod(stars, 5)
    return "🌟" * big_stars + "⭐" * small_stars


def reinforce_label(name: str, level: int) -> str:
    stars = star_count(level)
    if stars <= 0:
        return f"{name} (Lv. {level})"
    return f"{name} {star_icons(stars)} (Lv. {level}, {stars}성)"


class admincmds(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for command in self.get_commands():
            command.add_check(self.checks.master)

    async def sendlog(self, ctx, action="ADMIN"):
        channel = self.client.get_channel(ADMIN_LOG_CHANNEL_ID)
        if channel is None:
            return
        try:
            now = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")
            await channel.send(
                embed=get_embed(
                    f"🛠️ {action}",
                    f"관리자: {ctx.author} (`{ctx.author.id}`)\n명령어: `{ctx.message.content}`\n시간: `{now}`",
                )
            )
        except discord.HTTPException:
            return

    async def ensure_user(self, cur, uid: int, *, adminuser: int = 0, blacklist: int = 0):
        await cur.execute("SELECT * FROM userdata WHERE id = %s", uid)
        row = await cur.fetchone()
        if row is not None:
            return False
        await cur.execute(
            "INSERT INTO userdata (id, money, bank, adminuser, blacklist) VALUES (%s, %s, %s, %s, %s)",
            (uid, "5000", "0", adminuser, blacklist),
        )
        return True

    async def ensure_inventory(self, cur):
        await cur.execute(
            "CREATE TABLE IF NOT EXISTS inventory (user_id BIGINT NOT NULL, item_key TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, item_key))"
        )

    async def add_inventory_item(self, cur, uid: int, item_key: str, amount: int):
        await self.ensure_inventory(cur)
        await cur.execute("SELECT amount FROM inventory WHERE user_id = %s AND item_key = %s", (uid, item_key))
        row = await cur.fetchone()
        if row is None:
            await cur.execute(
                "INSERT INTO inventory (user_id, item_key, amount) VALUES (%s, %s, %s)",
                (uid, item_key, amount),
            )
        else:
            await cur.execute(
                "UPDATE inventory SET amount = %s WHERE user_id = %s AND item_key = %s",
                (max(0, int(row["amount"]) + amount), uid, item_key),
            )

    def parse_reinforce_set_args(self, args):
        if len(args) < 2:
            return None, None
        first = args[0]
        last = args[-1]
        if first.lstrip("-").isdigit() and len(args) >= 2:
            level = int(first)
            name = " ".join(args[1:])
            return name, level
        if last.lstrip("-").isdigit():
            level = int(last)
            name = " ".join(args[:-1])
            return name, level
        return None, None

    @commands.command(name="관리자도움", aliases=["어드민도움", "관리도움"])
    async def admin_help(self, ctx):
        embed = get_embed("🛠️ 관리자 명령어")
        embed.add_field(name="유저", value="`강제가입 <uid>`, `유저등록확인 <uid>`, `어드민추가 <uid>`, `어드민제거 <uid>`, `블랙추가 <uid>`, `블랙제거 <uid>`", inline=False)
        embed.add_field(name="경제", value="`돈설정 <uid> <금액>`, `돈지급 <uid> <금액>`, `돈차감 <uid> <금액>`, `은행설정 <uid> <금액>`", inline=False)
        embed.add_field(name="강화", value="`강화설정 <uid> <이름> <레벨>` 또는 `강화설정 <uid> <레벨> <이름>`, `강화삭제 <uid> <이름>`, `강화목록확인 <uid>`", inline=False)
        embed.add_field(name="상점", value="`아이템지급 <uid> <아이템명> <개수>`, `아이템회수 <uid> <아이템명> <개수>`, `인벤확인 <uid>`", inline=False)
        embed.add_field(name="공지", value="`공지보내 <내용>`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="강제가입")
    async def force_register(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                created = await self.ensure_user(cur, uid)
        await ctx.send(embed=get_embed("✅ 강제가입", f"uid: `{uid}`\n결과: {'새로 등록됨' if created else '이미 등록됨'}"))
        await self.sendlog(ctx, "FORCE REGISTER")

    @commands.command(name="유저등록확인")
    async def check_user_existing(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, money, bank, adminuser, blacklist FROM userdata WHERE id = %s", uid)
                row = await cur.fetchone()
        if row is None:
            await ctx.send(embed=get_embed("❓ 미등록 유저", f"uid `{uid}`는 등록되어 있지 않습니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed(
            "✅ 등록 유저",
            f"uid: `{row['id']}`\n지갑: {format_money(int(row['money']))}\n은행: {format_money(int(row['bank']))}\nadminuser: `{row['adminuser']}`\nblacklist: `{row['blacklist']}`",
        ))
        await self.sendlog(ctx, "CHECK USER")

    @commands.command(name="어드민추가")
    async def add_admin(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                created = await self.ensure_user(cur, uid, adminuser=1)
                if not created:
                    await cur.execute("UPDATE userdata SET adminuser = 1 WHERE id = %s", (uid,))
        await ctx.send(embed=get_embed("✅ 어드민 추가", f"uid `{uid}`를 관리자 권한으로 설정했습니다."))
        await self.sendlog(ctx, "ADD ADMIN")

    @commands.command(name="어드민제거")
    async def remove_admin(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                affected = await cur.execute("UPDATE userdata SET adminuser = 0 WHERE id = %s", (uid,))
        if affected == 0:
            await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed("✅ 어드민 제거", f"uid `{uid}`의 관리자 권한을 제거했습니다."))
        await self.sendlog(ctx, "REMOVE ADMIN")

    @commands.command(name="블랙추가")
    async def add_blacklist(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                created = await self.ensure_user(cur, uid, blacklist=1)
                if not created:
                    await cur.execute("UPDATE userdata SET blacklist = 1 WHERE id = %s", (uid,))
        await ctx.send(embed=get_embed("✅ 블랙리스트 추가", f"uid `{uid}`를 블랙리스트로 설정했습니다."))
        await self.sendlog(ctx, "ADD BLACKLIST")

    @commands.command(name="블랙제거")
    async def remove_blacklist(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                affected = await cur.execute("UPDATE userdata SET blacklist = 0 WHERE id = %s", (uid,))
        if affected == 0:
            await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed("✅ 블랙리스트 제거", f"uid `{uid}`의 블랙리스트를 해제했습니다."))
        await self.sendlog(ctx, "REMOVE BLACKLIST")

    @commands.command(name="돈설정")
    async def money_set(self, ctx, uid: int, amount: int):
        if amount < 0:
            await ctx.send(embed=get_embed("금액 오류", "금액은 0 이상이어야 합니다.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                affected = await cur.execute("UPDATE userdata SET money = %s WHERE id = %s", (str(amount), uid))
        if affected == 0:
            await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed("✅ 돈 설정", f"uid `{uid}` 지갑을 {format_money(amount)}으로 설정했습니다."))
        await self.sendlog(ctx, "SET MONEY")

    @commands.command(name="돈지급")
    async def money_add(self, ctx, uid: int, amount: int):
        if amount <= 0:
            await ctx.send(embed=get_embed("금액 오류", "금액은 1 이상이어야 합니다.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT money FROM userdata WHERE id = %s", uid)
                row = await cur.fetchone()
                if row is None:
                    await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
                    return
                new_money = int(row["money"]) + amount
                await cur.execute("UPDATE userdata SET money = %s WHERE id = %s", (str(new_money), uid))
        await ctx.send(embed=get_embed("✅ 돈 지급", f"uid `{uid}`에게 {format_money(amount)}을 지급했습니다."))
        await self.sendlog(ctx, "ADD MONEY")

    @commands.command(name="돈차감")
    async def money_subtract(self, ctx, uid: int, amount: int):
        if amount <= 0:
            await ctx.send(embed=get_embed("금액 오류", "금액은 1 이상이어야 합니다.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT money FROM userdata WHERE id = %s", uid)
                row = await cur.fetchone()
                if row is None:
                    await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
                    return
                new_money = max(0, int(row["money"]) - amount)
                await cur.execute("UPDATE userdata SET money = %s WHERE id = %s", (str(new_money), uid))
        await ctx.send(embed=get_embed("✅ 돈 차감", f"uid `{uid}`에게서 {format_money(amount)}을 차감했습니다."))
        await self.sendlog(ctx, "SUBTRACT MONEY")

    @commands.command(name="은행설정")
    async def bank_set(self, ctx, uid: int, amount: int):
        if amount < 0:
            await ctx.send(embed=get_embed("금액 오류", "금액은 0 이상이어야 합니다.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                affected = await cur.execute("UPDATE userdata SET bank = %s WHERE id = %s", (str(amount), uid))
        if affected == 0:
            await ctx.send(embed=get_embed("❓ 대상 없음", "등록되지 않은 유저입니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed("✅ 은행 설정", f"uid `{uid}` 은행 잔고를 {format_money(amount)}으로 설정했습니다."))
        await self.sendlog(ctx, "SET BANK")

    @commands.command(name="강화설정")
    async def reinforce_set(self, ctx, uid: int, *args):
        name, level = self.parse_reinforce_set_args(args)
        if name is None or level is None:
            await ctx.send(embed=get_embed("사용법", "알티야 강화설정 <uid> <이름> <레벨> 또는 알티야 강화설정 <uid> <레벨> <이름>", 0xFF0000))
            return
        if level < 0:
            await ctx.send(embed=get_embed("레벨 오류", "레벨은 0 이상이어야 합니다.", 0xFF0000))
            return
        valid, name_or_error = validate_item_name(name)
        if not valid:
            await ctx.send(embed=get_embed("이름 오류", name_or_error, 0xFF0000))
            return
        name = name_or_error
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_user(cur, uid)
                if await cur.execute("SELECT * FROM reinforce WHERE id = %s AND name = %s", (uid, name)) == 0:
                    await cur.execute("INSERT INTO reinforce (uuid, name, id, level) VALUES (%s, %s, %s, %s)", (uuid.uuid4().hex, name, uid, level))
                    action = "생성"
                else:
                    await cur.execute("UPDATE reinforce SET level = %s WHERE id = %s AND name = %s", (level, uid, name))
                    action = "수정"
        await ctx.send(embed=get_embed("✅ 강화 설정", f"{action}: uid `{uid}`\n{reinforce_label(name, level)}"))
        await self.sendlog(ctx, "SET REINFORCE")

    @commands.command(name="강화삭제")
    async def reinforce_delete(self, ctx, uid: int, *, name: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                affected = await cur.execute("DELETE FROM reinforce WHERE id = %s AND name = %s", (uid, name.strip()))
        if affected == 0:
            await ctx.send(embed=get_embed("❓ 대상 없음", "해당 강화 아이템을 찾을 수 없습니다.", 0xFF0000))
            return
        await ctx.send(embed=get_embed("✅ 강화 삭제", f"uid `{uid}`의 `{name}`을 삭제했습니다."))
        await self.sendlog(ctx, "DELETE REINFORCE")

    @commands.command(name="강화목록확인")
    async def reinforce_list(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT name, level FROM reinforce WHERE id = %s ORDER BY level DESC", uid)
                rows = await cur.fetchall()
        if not rows:
            await ctx.send(embed=get_embed("📦 강화 목록", "강화 아이템이 없습니다."))
            return
        text = "\n".join(reinforce_label(row["name"], int(row["level"])) for row in rows)
        await ctx.send(embed=get_embed(f"📦 uid {uid} 강화 목록", text))

    @commands.command(name="아이템지급")
    async def item_add(self, ctx, uid: int, item_name: str, amount: int = 1):
        if amount <= 0:
            await ctx.send(embed=get_embed("개수 오류", "개수는 1 이상이어야 합니다.", 0xFF0000))
            return
        item_key = resolve_item_key(item_name)
        item = get_item(item_key)
        if item is None:
            await ctx.send(embed=get_embed("없는 아이템", "알티야 상점에서 아이템 이름을 확인해주세요.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_user(cur, uid)
                await self.add_inventory_item(cur, uid, item_key, amount)
        await ctx.send(embed=get_embed("✅ 아이템 지급", f"uid `{uid}`에게 {item['name']} {amount:,}개를 지급했습니다."))
        await self.sendlog(ctx, "ADD ITEM")

    @commands.command(name="아이템회수")
    async def item_remove(self, ctx, uid: int, item_name: str, amount: int = 1):
        if amount <= 0:
            await ctx.send(embed=get_embed("개수 오류", "개수는 1 이상이어야 합니다.", 0xFF0000))
            return
        item_key = resolve_item_key(item_name)
        item = get_item(item_key)
        if item is None:
            await ctx.send(embed=get_embed("없는 아이템", "알티야 상점에서 아이템 이름을 확인해주세요.", 0xFF0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_inventory(cur)
                await self.add_inventory_item(cur, uid, item_key, -amount)
        await ctx.send(embed=get_embed("✅ 아이템 회수", f"uid `{uid}`에게서 {item['name']} {amount:,}개를 회수했습니다."))
        await self.sendlog(ctx, "REMOVE ITEM")

    @commands.command(name="인벤확인")
    async def inventory_check(self, ctx, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_inventory(cur)
                await cur.execute("SELECT item_key, amount FROM inventory WHERE user_id = %s AND amount > 0 ORDER BY item_key", uid)
                rows = await cur.fetchall()
        if not rows:
            await ctx.send(embed=get_embed("🎒 인벤토리", "보유 아이템이 없습니다."))
            return
        lines = []
        for row in rows:
            item = get_item(row["item_key"])
            name = item["name"] if item else row["item_key"]
            lines.append(f"{name}: {int(row['amount']):,}개")
        await ctx.send(embed=get_embed(f"🎒 uid {uid} 인벤토리", "\n".join(lines)))

    def choose_notice_channel(self, guild):
        if str(guild.id) in noticedb:
            channel = self.client.get_channel(noticedb[str(guild.id)])
            if channel and channel.permissions_for(guild.me).send_messages:
                return channel
        fallback_channel = None
        for channel in guild.text_channels:
            if not channel.permissions_for(guild.me).send_messages:
                continue
            if fallback_channel is None:
                fallback_channel = channel
            lower_name = channel.name.lower()
            if ("공지" in channel.name and "봇" in channel.name) or ("noti" in lower_name and "bot" in lower_name):
                return channel
            if "공지" in channel.name or "noti" in lower_name or "봇" in channel.name or "bot" in lower_name:
                return channel
        return fallback_channel

    @commands.command(name="공지보내")
    async def notice_send(self, ctx, *, arg):
        preview = get_embed(
            "<a:waiting:712170404869046334> ｜ 알티봇 공지",
            arg + "\n\n모든 문의, 건의는 알티봇 서포트 서버에서 해주세요.\n알티봇 초대하기 링크는 기존 초대 링크를 사용해주세요.",
        )
        confirmed, _ = await ask_confirm(
            ctx,
            embed=get_embed("📣 전체 공지 확인", f"대상 서버 수: {len(self.client.guilds):,}\n아래 내용으로 전체 공지를 전송하시겠습니까?"),
            timeout=45,
        )
        if confirmed is not True:
            await ctx.send(embed=get_embed("❌ 공지 취소", "공지 전송이 취소되었습니다.", 0xFF0000))
            return

        success_list = ["SUCCEED LIST"]
        fail_list = ["FAIL LIST"]
        control = await ctx.send(embed=get_embed("공지 전송중", "준비 중..."))

        for guild in self.client.guilds:
            channel = self.choose_notice_channel(guild)
            try:
                if channel is None:
                    raise RuntimeError("No writable channel found")
                await channel.send(embed=preview)
                success_list.append(f"성공 {guild.name} ({guild.id}) -> #{channel.name}")
            except Exception as exc:
                fail_list.append(f"실패 {guild.name} ({guild.id}) -> {type(exc).__name__}: {exc}")
            await control.edit(embed=get_embed("공지 전송중", f"성공: {len(success_list) - 1}\n실패: {len(fail_list) - 1}"))
            await asyncio.sleep(0.4)

        logfile = discord.File(fp=io.StringIO("\n".join(success_list) + "\n\n" + "\n".join(fail_list)), filename="notilog.log")
        await ctx.send(embed=get_embed("✅ 공지 전송 완료", f"성공: {len(success_list) - 1}\n실패: {len(fail_list) - 1}"), file=logfile)
        await self.sendlog(ctx, "SEND NOTICE")


async def setup(client):
    await client.add_cog(admincmds(client))
