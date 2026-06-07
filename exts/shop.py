import asyncio

import aiomysql
import discord
from discord.ext import commands

from utils import checks
from utils.shop_items import SHOP_ITEMS, format_money, get_item, resolve_item_key
from utils.views import ask_confirm


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


class Shop(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for command in self.get_commands():
            command.add_check(self.checks.registered)
            command.add_check(self.checks.blacklist)

    async def ensure_table(self, cur):
        await cur.execute(
            'CREATE TABLE IF NOT EXISTS inventory ('
            'user_id BIGINT NOT NULL, '
            'item_key TEXT NOT NULL, '
            'amount INTEGER NOT NULL DEFAULT 0, '
            'PRIMARY KEY (user_id, item_key)'
            ')'
        )
        await cur.execute(
            'CREATE TABLE IF NOT EXISTS reinforce_rate_bonus ('
            'user_id BIGINT NOT NULL, '
            'item_name TEXT NOT NULL, '
            'bonus INTEGER NOT NULL DEFAULT 0, '
            'PRIMARY KEY (user_id, item_name)'
            ')'
        )

    async def add_item(self, cur, user_id, item_key, amount):
        await cur.execute(
            'SELECT amount FROM inventory WHERE user_id = %s AND item_key = %s',
            (user_id, item_key),
        )
        row = await cur.fetchone()

        if row is None:
            await cur.execute(
                'INSERT INTO inventory (user_id, item_key, amount) VALUES (%s, %s, %s)',
                (user_id, item_key, amount),
            )
        else:
            await cur.execute(
                'UPDATE inventory SET amount = %s WHERE user_id = %s AND item_key = %s',
                (int(row['amount']) + amount, user_id, item_key),
            )

    async def refund_money(self, cur, user_id, amount):
        await cur.execute('SELECT money FROM userdata WHERE id = %s', user_id)
        row = await cur.fetchone()
        money = int(row['money'])
        await cur.execute(
            'UPDATE userdata SET money = %s WHERE id = %s',
            (str(money + amount), user_id),
        )

    async def apply_rate_bonus(self, cur, user_id, item_name, bonus):
        item_name = item_name.strip()

        if await cur.execute(
            'SELECT name FROM reinforce WHERE id = %s AND name = %s',
            (user_id, item_name),
        ) == 0:
            return None

        await cur.execute(
            'SELECT bonus FROM reinforce_rate_bonus WHERE user_id = %s AND item_name = %s',
            (user_id, item_name),
        )
        row = await cur.fetchone()

        if row is None:
            await cur.execute(
                'INSERT INTO reinforce_rate_bonus (user_id, item_name, bonus) VALUES (%s, %s, %s)',
                (user_id, item_name, bonus),
            )
            return bonus

        new_bonus = int(row['bonus']) + bonus
        await cur.execute(
            'UPDATE reinforce_rate_bonus SET bonus = %s WHERE user_id = %s AND item_name = %s',
            (new_bonus, user_id, item_name),
        )
        return new_bonus

    async def ask_target_item_name(self, ctx, item, total_bonus, total_price):
        await ctx.send(
            embed=get_embed(
                '🎯 적용할 강화 아이템 입력',
                (
                    f"{item['name']} 구매가 완료되었습니다.\n"
                    f"적용할 강화 아이템 이름을 30초 안에 입력해주세요.\n\n"
                    f"적용 효과: 일반 강화 성공률 영구 +{total_bonus}%\n"
                    f"취소하거나 시간 초과되면 {format_money(total_price)}이 환불됩니다."
                ),
            )
        )

        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel

        try:
            message = await self.client.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            return None, 'timeout'

        target_name = message.content.strip()

        if target_name in {'취소', 'cancel', 'Cancel', 'x', 'X', '0'}:
            return None, 'cancel'

        return target_name, None

    @commands.command(name='상점', aliases=['샵'])
    async def shop(self, ctx):
        lines = []

        for item in SHOP_ITEMS.values():
            lines.append(
                f"**{item['name']}** — {format_money(item['price'])}\n"
                f"{item['description']}"
            )

        await ctx.send(embed=get_embed('🛒 상점', '\n\n'.join(lines)))

    @commands.command(name='구매', aliases=['구입'])
    async def buy(self, ctx, item_name: str, amount: int = 1):
        if amount <= 0 or amount > 99:
            await ctx.send(
                embed=get_embed(
                    '구매 불가',
                    '구매 개수는 1개 이상 99개 이하여야 합니다.',
                    0xFF0000,
                )
            )
            return

        item_key = resolve_item_key(item_name)
        item = get_item(item_key)

        if item is None:
            await ctx.send(
                embed=get_embed(
                    '없는 아이템입니다',
                    '알티야 상점에서 아이템 이름을 확인해주세요.',
                    0xFF0000,
                )
            )
            return

        total_price = int(item['price']) * amount
        total_bonus = int(item.get('rate_bonus', 0)) * amount

        confirmed, _ = await ask_confirm(
            ctx,
            embed=get_embed(
                '🛒 구매 확인',
                f"{item['name']} {amount:,}개\n총 가격: {format_money(total_price)}",
            ),
            timeout=30,
        )

        if not confirmed:
            await ctx.send(embed=get_embed('구매 취소', '구매가 취소되었습니다.', 0xFF0000))
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_table(cur)
                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                row = await cur.fetchone()
                money = int(row['money'])

                if money < total_price:
                    await ctx.send(
                        embed=get_embed(
                            '돈이 부족합니다',
                            f'필요 금액: {format_money(total_price)}\n현재 지갑: {format_money(money)}',
                            0xFF0000,
                        )
                    )
                    return

                await cur.execute(
                    'UPDATE userdata SET money = %s WHERE id = %s',
                    (str(money - total_price), ctx.author.id),
                )

        if item.get('apply_on_purchase'):
            target_name, fail_reason = await self.ask_target_item_name(
                ctx,
                item,
                total_bonus,
                total_price,
            )

            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await self.ensure_table(cur)

                    if target_name is None:
                        await self.refund_money(cur, ctx.author.id, total_price)
                        reason_text = '시간이 초과되었습니다.' if fail_reason == 'timeout' else '구매가 취소되었습니다.'
                        await ctx.send(
                            embed=get_embed(
                                '💸 구매 환불',
                                f'{reason_text}\n{format_money(total_price)}이 환불되었습니다.',
                                0xFF0000,
                            )
                        )
                        return

                    new_bonus = await self.apply_rate_bonus(
                        cur,
                        ctx.author.id,
                        target_name,
                        total_bonus,
                    )

                    if new_bonus is None:
                        await self.refund_money(cur, ctx.author.id, total_price)
                        await ctx.send(
                            embed=get_embed(
                                '💸 구매 환불',
                                (
                                    f'`{target_name}` 아이템을 찾을 수 없습니다.\n'
                                    f'{format_money(total_price)}이 환불되었습니다.'
                                ),
                                0xFF0000,
                            )
                        )
                        return

            await ctx.send(
                embed=get_embed(
                    '✅ 구매 및 적용 완료',
                    (
                        f"{item['name']} {amount:,}개를 구매했습니다.\n"
                        f"`{target_name}`의 일반 강화 성공률이 영구적으로 +{total_bonus}% 증가했습니다.\n"
                        f"현재 영구 보너스: +{new_bonus}%"
                    ),
                )
            )
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_table(cur)
                await self.add_item(cur, ctx.author.id, item_key, amount)

        await ctx.send(
            embed=get_embed(
                '✅ 구매 완료',
                f"{item['name']} {amount:,}개를 구매했습니다.",
            )
        )

    @commands.command(name='인벤토리', aliases=['인벤', '아이템'])
    async def inventory(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_table(cur)
                await cur.execute(
                    'SELECT item_key, amount FROM inventory WHERE user_id = %s AND amount > 0 ORDER BY item_key',
                    ctx.author.id,
                )
                rows = await cur.fetchall()

        if not rows:
            await ctx.send(embed=get_embed('🎒 인벤토리', '보유 중인 아이템이 없습니다.'))
            return

        lines = []

        for row in rows:
            item = get_item(row['item_key'])

            if item is None:
                continue

            lines.append(f'{item["name"]}: {int(row["amount"]):,}개')

        if not lines:
            await ctx.send(embed=get_embed('🎒 인벤토리', '보유 중인 아이템이 없습니다.'))
            return

        await ctx.send(embed=get_embed('🎒 인벤토리', '\n'.join(lines)))


async def setup(client):
    await client.add_cog(Shop(client))
