import random
import uuid
from random import randint

import aiomysql
import discord
from discord.ext import commands

from utils import checks
from utils.views import ask_confirm

STAR_LEVEL_BASE = 100
DESTROY_LEVEL = 90
MIN_ITEM_NAME_LENGTH = 2
MAX_ITEM_NAME_LENGTH = 15
BLOCKED_STAR_EMOJIS = {'⭐', '🌟', '✨', '💫', '🌠', '✴️', '✳️', '❇️', '✡️'}


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


def star_count(level: int) -> int:
    if level < STAR_LEVEL_BASE:
        return 0
    return level - STAR_LEVEL_BASE


def star_icons(stars: int) -> str:
    if stars <= 0:
        return ''
    big_stars, small_stars = divmod(stars, 5)
    return '🌟' * big_stars + '⭐' * small_stars


def item_label(name: str, level: int) -> str:
    stars = star_count(level)
    if stars <= 0:
        return f'{name} (Lv. {level})'
    return f'{name} {star_icons(stars)} (Lv. {level}, {stars}성)'


def validate_item_name(name: str):
    stripped = name.strip()
    if len(stripped) < MIN_ITEM_NAME_LENGTH or len(stripped) > MAX_ITEM_NAME_LENGTH:
        return False, f'아이템 이름은 {MIN_ITEM_NAME_LENGTH}글자 이상 {MAX_ITEM_NAME_LENGTH}자 이내여야 합니다.'
    if any(star in stripped for star in BLOCKED_STAR_EMOJIS):
        return False, '아이템 이름에는 별 이모지를 사용할 수 없습니다.'
    return True, stripped


def star_rate(stars: int):
    rates = {
        0: (90, 10, 0),
        1: (80, 20, 0),
        2: (70, 30, 0),
        3: (60, 40, 0),
        4: (50, 50, 0),
        5: (40, 50, 10),
        6: (30, 50, 20),
        7: (20, 50, 30),
    }
    return rates.get(stars, (10, 50, 40))


def roll_starforce(stars: int):
    success, fail, destroy = star_rate(stars)
    roll = randint(1, 100)
    if roll <= success:
        return 'success', success, fail, destroy
    if roll <= success + fail:
        return 'fail', success, fail, destroy
    return 'destroy', success, fail, destroy


def reinforce_sell_price(level: int) -> int:
    if level < 60:
        return 0
    if level < 80:
        return 80_000 + (level - 60) * 4_000
    if level < 90:
        return 300_000 + (level - 80) * 70_000
    if level <= 100:
        return 1_000_000 + (level - 90) * 100_000
    if level < 105:
        return 2_000_000 + (level - 100) * 2_000_000
    return 20_000_000 * (2 ** (level - 105))


def normal_success_rate(level: int) -> int:
    base = max(8, 100 - level)

    if level >= 60:
        base += 2

    if level >= 70:
        base += 2

    if level >= 80:
        base += 2

    return min(base, 100)


def normal_gain(level: int) -> int:
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    if level < 30:
        return random.choices(
            values,
            weights=[1, 1, 2, 3, 5, 8, 12, 20, 24, 24],
            k=1,
        )[0]

    if level < 70:
        return random.choices(
            values,
            weights=[1, 2, 8, 14, 18, 18, 16, 13, 6, 4],
            k=1,
        )[0]

    if level < 90:
        return random.choices(
            values,
            weights=[4, 6, 10, 10, 7, 4, 3, 2, 1, 1],
            k=1,
        )[0]

    return random.choices(
        values,
        weights=[5, 8, 10, 7, 5, 4, 3, 2, 1, 1],
        k=1,
    )[0]


def normal_loss(level: int) -> int:
    if level < 30:
        return random.choices(
            [1, 2],
            weights=[85, 15],
            k=1,
        )[0]

    if level < 70:
        return random.choices(
            [1, 2, 3, 4],
            weights=[35, 30, 25, 10],
            k=1,
        )[0]

    if level < 90:
        return random.choices(
            [1, 2, 3],
            weights=[50, 35, 15],
            k=1,
        )[0]

    return random.choices(
        [1, 2, 3],
        weights=[65, 30, 5],
        k=1,
    )[0]


def normal_fail_floor(level: int) -> int:
    if level >= 90:
        return 85
    if level >= 70:
        return 60
    return 0


def roll_normal_reinforce(level: int):
    rate = normal_success_rate(level)
    if randint(1, 100) <= rate:
        gain = normal_gain(level)
        new_level = min(STAR_LEVEL_BASE, level + gain)
        return 'success', new_level, gain, rate

    loss = normal_loss(level)
    new_level = max(normal_fail_floor(level), level - loss)
    return 'fail', new_level, loss, rate


class reinforce(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.blacklist)

    @commands.group(name='강화', aliases=['강'], invoke_without_command=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def _reinforce(self, ctx, *, weapon):
        is_valid_name, item_name_or_error = validate_item_name(weapon)
        if not is_valid_name:
            await ctx.send(embed=get_embed('🛠️ 강화 이름 오류', item_name_or_error, 0xFF0000))
            return

        weapon = item_name_or_error
        user = ctx.author.id

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if await cur.execute('SELECT * FROM reinforce WHERE id = %s and name = %s', (user, weapon)) == 0:
                    await cur.execute('SELECT * FROM reinforce WHERE id = %s', user)
                    items = await cur.fetchall()
                    if len(items) >= 20:
                        await ctx.send(embed=get_embed('📦 강화 개수 초과', '강화는 최대 20개까지 가능합니다.', 0xFF0000))
                        return
                    await cur.execute('INSERT INTO reinforce VALUES (%s, %s, %s, %s)', (uuid.uuid4().hex, weapon, user, 0))

                await cur.execute('SELECT level FROM reinforce WHERE id = %s and name = %s', (user, weapon))
                row = await cur.fetchone()
                level = int(row['level'])
                current_label = item_label(weapon, level)

                if level >= STAR_LEVEL_BASE:
                    stars = star_count(level)
                    success, fail, destroy = star_rate(stars)
                    destroy_text = f' / 파괴 {destroy}%' if destroy else ''
                    confirmed, _ = await ask_confirm(
                        ctx,
                        embed=get_embed(
                            '🌟 스타강화',
                            f'{current_label}\n\n{stars}성 → {stars + 1}성\n성공 {success}% / 실패 {fail}%{destroy_text}\n\n도전하시겠습니까?',
                        ),
                        timeout=30,
                    )
                    if confirmed is None:
                        await ctx.send(embed=get_embed('⏰ 시간 초과', '스타강화가 취소되었습니다.', 0xFF0000))
                        return
                    if confirmed is False:
                        await ctx.send(embed=get_embed('❌ 취소됨', '스타강화가 취소되었습니다.', 0xFF0000))
                        return

                    result, success, fail, destroy = roll_starforce(stars)
                    if result == 'success':
                        new_level = level + 1
                        await cur.execute('UPDATE reinforce SET level = %s WHERE id = %s and name = %s', (new_level, ctx.author.id, weapon))
                        await ctx.send(embed=get_embed('✨ 스타강화 성공', f'{item_label(weapon, new_level)}\n{stars}성 → {stars + 1}성'))
                    elif result == 'fail':
                        new_level = max(STAR_LEVEL_BASE, level - 1)
                        await cur.execute('UPDATE reinforce SET level = %s WHERE id = %s and name = %s', (new_level, ctx.author.id, weapon))
                        await ctx.send(embed=get_embed('💥 스타강화 실패', f'{item_label(weapon, new_level)}\n{stars}성 → {star_count(new_level)}성', 0xFF0000))
                    else:
                        new_level = DESTROY_LEVEL
                        await cur.execute('UPDATE reinforce SET level = %s WHERE id = %s and name = %s', (new_level, ctx.author.id, weapon))
                        await ctx.send(embed=get_embed('💣 스타강화 파괴', f'{weapon}이 파괴되어 0성 90레벨로 돌아갔습니다.\n{item_label(weapon, new_level)}', 0xFF0000))
                    return

                result, new_level, amount, rate = roll_normal_reinforce(level)
                if result == 'success':
                    await cur.execute('UPDATE reinforce SET level = %s WHERE id = %s and name = %s', (new_level, ctx.author.id, weapon))
                    await ctx.send(embed=get_embed(
                        '🔨 강화 성공',
                        f'{item_label(weapon, new_level)}\n+{amount}레벨 성장했습니다.\n성공 확률: {rate}%',
                    ))
                else:
                    await cur.execute('UPDATE reinforce SET level = %s WHERE id = %s and name = %s', (new_level, ctx.author.id, weapon))
                    await ctx.send(embed=get_embed(
                        '🧱 강화 실패',
                        f'{item_label(weapon, new_level)}\n-{amount}레벨 하락했습니다.\n성공 확률: {rate}%',
                        0xFF0000,
                    ))

    @_reinforce.command(name='목록', aliases=['물품', '리스트'])
    async def _rf_list(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM reinforce WHERE id = %s ORDER BY level DESC', ctx.author.id)
                rows = await cur.fetchall()
        if not rows:
            await ctx.send(embed=get_embed('📦 강화 목록', '아직 강화 아이템이 없습니다.'))
            return
        text = '\n'.join(item_label(row['name'], int(row['level'])) for row in rows)
        await ctx.send(embed=get_embed(f'📦 {ctx.author} 님의 강화 목록', text))

    @_reinforce.command(name='삭제')
    async def _rf_erase(self, ctx, *, arg):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if await cur.execute('SELECT * FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg)) == 0:
                    await ctx.send(embed=get_embed('❓ 찾을 수 없는 물품입니다.', '', 0xFF0000))
                    return

                await cur.execute('SELECT level FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg))
                row = await cur.fetchone()
                level = int(row['level'])
                label = item_label(arg, level)

                confirmed, _ = await ask_confirm(
                    ctx,
                    embed=get_embed('🗑️ 강화 삭제', f'{label}\n정말 삭제하시겠습니까?'),
                    timeout=30,
                )
                if confirmed is None:
                    await ctx.send(embed=get_embed('⏰ 시간 초과', '삭제가 취소되었습니다.', 0xFF0000))
                    return
                if confirmed is False:
                    await ctx.send(embed=get_embed('❌ 취소됨', '삭제가 취소되었습니다.', 0xFF0000))
                    return

                await cur.execute('DELETE FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg))
        await ctx.send(embed=get_embed('✅ 삭제 완료', label))

    @_reinforce.command(name='판매')
    async def _rf_sell(self, ctx, *, arg):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if await cur.execute('SELECT * FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg)) == 0:
                    await ctx.send(embed=get_embed('❓ 찾을 수 없는 물품입니다.', '', 0xFF0000))
                    return

                await cur.execute('SELECT level FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg))
                row = await cur.fetchone()
                level = int(row['level'])
                if level < 60:
                    await ctx.send(embed=get_embed('💰 판매 불가', '60레벨 이상의 물품만 판매할 수 있습니다.', 0xFF0000))
                    return

                price = reinforce_sell_price(level)
                label = item_label(arg, level)
                confirmed, _ = await ask_confirm(
                    ctx,
                    embed=get_embed('💰 강화 판매', f'{label}\n판매가: {price:,}원\n정말 판매하시겠습니까?'),
                    timeout=30,
                )
                if confirmed is None:
                    await ctx.send(embed=get_embed('⏰ 시간 초과', '판매가 취소되었습니다.', 0xFF0000))
                    return
                if confirmed is False:
                    await ctx.send(embed=get_embed('❌ 취소됨', '판매가 취소되었습니다.', 0xFF0000))
                    return

                await cur.execute('DELETE FROM reinforce WHERE id = %s and name = %s', (ctx.author.id, arg))
                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                money_row = await cur.fetchone()
                money = int(money_row['money'])
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(money + price), ctx.author.id))
        await ctx.send(embed=get_embed('✅ 판매 완료', f'{label}\n{price:,}원이 지급되었습니다.'))

    @_reinforce.group(name='순위', invoke_without_command=True)
    async def _rf_rank(self, ctx):
        await ctx.send(embed=get_embed('📊 올바르지 않은 명령어입니다.', '알티야 강화 순위 서버/전체로 사용해주세요.', 0xFF0000))

    @_rf_rank.command(name='서버')
    async def _rf_list_server(self, ctx):
        ranking = []
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM reinforce ORDER BY level DESC')
                rows = await cur.fetchall()
        for row in rows:
            member = ctx.guild.get_member(int(row['id']))
            if member is not None:
                ranking.append([member.name, row['name'], int(row['level'])])
            if len(ranking) >= 6:
                break
        text = '\n\n'.join(f'{idx + 1}위 | {name}\n{item_label(item, level)}' for idx, (name, item, level) in enumerate(ranking))
        await ctx.send(embed=get_embed('📊 서버 강화 순위', text or '표시할 강화 기록이 없습니다.'))

    @_rf_rank.command(name='전체')
    async def _rf_list_all(self, ctx):
        ranking = []
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM reinforce ORDER BY level DESC LIMIT 6')
                rows = await cur.fetchall()
        for row in rows:
            user = self.client.get_user(int(row['id']))
            ranking.append([user.name if user else str(row['id']), row['name'], int(row['level'])])
        text = '\n\n'.join(f'{idx + 1}위 | {name}\n{item_label(item, level)}' for idx, (name, item, level) in enumerate(ranking))
        await ctx.send(embed=get_embed('📊 전체 강화 순위', text or '표시할 강화 기록이 없습니다.'))


async def setup(client):
    await client.add_cog(reinforce(client))
