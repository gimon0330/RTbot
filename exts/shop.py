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
        await cur.execute('CREATE TABLE IF NOT EXISTS inventory (user_id BIGINT NOT NULL, item_key TEXT NOT NULL, amount INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (user_id, item_key))')

    async def add_item(self, cur, user_id, item_key, amount):
        await cur.execute('SELECT amount FROM inventory WHERE user_id = %s AND item_key = %s', (user_id, item_key))
        row = await cur.fetchone()
        if row is None:
            await cur.execute('INSERT INTO inventory (user_id, item_key, amount) VALUES (%s, %s, %s)', (user_id, item_key, amount))
        else:
            await cur.execute('UPDATE inventory SET amount = %s WHERE user_id = %s AND item_key = %s', (int(row['amount']) + amount, user_id, item_key))

    @commands.command(name='상점', aliases=['샵'])
    async def shop(self, ctx):
        lines = []
        for item in SHOP_ITEMS.values():
            lines.append(f"**{item['name']}** — {format_money(item['price'])}\n{item['description']}")
        await ctx.send(embed=get_embed('🛒 상점', '\n\n'.join(lines)))

    @commands.command(name='구매', aliases=['구입'])
    async def buy(self, ctx, item_name: str, amount: int = 1):
        if amount <= 0 or amount > 99:
            await ctx.send(embed=get_embed('구매 불가', '구매 개수는 1개 이상 99개 이하여야 합니다.', 0xFF0000))
            return
        item_key = resolve_item_key(item_name)
        item = get_item(item_key)
        if item is None:
            await ctx.send(embed=get_embed('없는 아이템입니다', '알티야 상점에서 아이템 이름을 확인해주세요.', 0xFF0000))
            return
        total_price = int(item['price']) * amount
        confirmed, _ = await ask_confirm(ctx, embed=get_embed('🛒 구매 확인', f"{item['name']} {amount:,}개\n총 가격: {format_money(total_price)}"), timeout=30)
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
                    await ctx.send(embed=get_embed('돈이 부족합니다', f'필요 금액: {format_money(total_price)}\n현재 지갑: {format_money(money)}', 0xFF0000))
                    return
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(money - total_price), ctx.author.id))
                await self.add_item(cur, ctx.author.id, item_key, amount)
        await ctx.send(embed=get_embed('✅ 구매 완료', f"{item['name']} {amount:,}개를 구매했습니다."))

    @commands.command(name='인벤토리', aliases=['인벤', '아이템'])
    async def inventory(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_table(cur)
                await cur.execute('SELECT item_key, amount FROM inventory WHERE user_id = %s AND amount > 0 ORDER BY item_key', ctx.author.id)
                rows = await cur.fetchall()
        if not rows:
            await ctx.send(embed=get_embed('🎒 인벤토리', '보유 중인 아이템이 없습니다.'))
            return
        lines = []
        for row in rows:
            item = get_item(row['item_key'])
            name = item['name'] if item else row['item_key']
            lines.append(f'{name}: {int(row["amount"]):,}개')
        await ctx.send(embed=get_embed('🎒 인벤토리', '\n'.join(lines)))


async def setup(client):
    await client.add_cog(Shop(client))
