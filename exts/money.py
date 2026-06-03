import typing
from random import randint

import aiomysql
import discord
from discord.ext import commands

from utils import errors, checks
from utils.views import ask_confirm


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


def format_money(value):
    return f"{int(value):,}원"


class money(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        self._dobak.add_check(self.checks.money0up)
        self.dobak_all.add_check(self.checks.money0up)

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.blacklist)

    async def get_user_money(self, cur, user_id):
        await cur.execute('SELECT money, bank FROM userdata WHERE id = %s', user_id)
        row = await cur.fetchone()
        if row is None:
            raise errors.NotRegistered
        return int(row['money']), int(row['bank'])

    @commands.group(name='도박', invoke_without_command=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def _dobak(self, ctx, n: int):
        if n < 1:
            raise errors.morethan1

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, _ = await self.get_user_money(cur, ctx.author.id)
                if money_value < n:
                    raise errors.NoMoney

                rand = randint(0, 100)
                new_money = money_value
                result = '1배! 잔액이 유지되었습니다.'

                if rand <= 11:
                    loss = n * 2
                    new_money = max(0, money_value - loss)
                    result = f'-1배! {format_money(money_value - new_money)}을 잃었습니다.'
                elif rand <= 31:
                    new_money = money_value - n
                    result = f'0배! {format_money(n)}을 잃었습니다.'
                elif rand > 81:
                    new_money = money_value + n
                    result = f'2배! {format_money(n)}을 얻었습니다.'

                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(new_money), ctx.author.id))

        await ctx.send(embed=get_embed('도박 결과', f'{ctx.author.mention}\n{result}\n현재 지갑: {format_money(new_money)}'))

    @_dobak.command(name='전체', aliases=['올인', '올'])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def dobak_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, _ = await self.get_user_money(cur, ctx.author.id)
                if money_value <= 0:
                    raise errors.NoMoney

                rand = randint(0, 100)
                multiplier = 0
                if rand <= 40:
                    multiplier = 0
                elif rand <= 45:
                    multiplier = 0.2
                elif rand <= 50:
                    multiplier = 0.25
                elif rand <= 55:
                    multiplier = 0.5
                elif rand <= 90:
                    multiplier = 2
                elif rand <= 95:
                    multiplier = 3
                elif rand <= 98:
                    multiplier = 4
                else:
                    multiplier = 5

                new_money = int(money_value * multiplier)
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(new_money), ctx.author.id))

        await ctx.send(embed=get_embed('올인 결과', f'배율: {multiplier}배\n현재 지갑: {format_money(new_money)}'))

    @commands.command(name='돈내놔', aliases=['돈줘', '돈받기', 'ㄷㅂㄱ'])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def _give_me_money(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, _ = await self.get_user_money(cur, ctx.author.id)
                new_money = money_value + 400
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(new_money), ctx.author.id))
        await ctx.send(embed=get_embed('지급 완료', f'{ctx.author.mention} 400원을 받았습니다.\n현재 지갑: {format_money(new_money)}'))

    @commands.group(name='내돈', aliases=['지갑', '돈', '니돈', 'ㄴㄷ', 'ㄷ'], invoke_without_command=True)
    async def _mymoney(self, ctx, user: typing.Optional[discord.Member] = None):
        user = user or ctx.author
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, _ = await self.get_user_money(cur, user.id)
        await ctx.send(embed=get_embed(f'{user} 님의 지갑', format_money(money_value)))

    @_mymoney.command(name='한글')
    async def _mymoney_kor(self, ctx, user: typing.Optional[discord.Member] = None):
        user = user or ctx.author
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, _ = await self.get_user_money(cur, user.id)

        suffix = ['', '만', '억', '조', '경', '해', '자', '양', '구', '간', '정', '재', '극', '항하사', '아승기', '나유타', '불가사의', '무량대수']
        if money_value == 0:
            result = '0'
        else:
            parts = []
            index = 0
            while money_value > 0 and index < len(suffix):
                chunk = money_value % 10000
                if chunk:
                    parts.append(f'{chunk}{suffix[index]}')
                money_value //= 10000
                index += 1
            result = ' '.join(reversed(parts))
        await ctx.send(embed=get_embed(f'{user} 님의 지갑', f'{result} 원'))

    @commands.command(name='송금', aliases=['입금'])
    @commands.guild_only()
    async def _give_money(self, ctx, muser: discord.Member, n: int):
        if muser == ctx.author:
            await ctx.send(embed=get_embed('송금 불가', '본인에게 송금할 수 없습니다.', 0xFF0000))
            return
        if n <= 0:
            raise errors.morethan1

        try:
            sendmoney = int(n ** (3 / 4))
        except OverflowError:
            await ctx.send(embed=get_embed('송금 불가', '금액이 너무 큽니다.', 0xFF0000))
            return

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                sender_money, _ = await self.get_user_money(cur, ctx.author.id)
                receiver_money, _ = await self.get_user_money(cur, muser.id)

                if sender_money < n:
                    raise errors.NoMoney

                confirmed, _ = await ask_confirm(
                    ctx,
                    embed=get_embed(
                        '송금 확인',
                        f'{ctx.author.mention} → {muser.mention}\n송금 금액: {format_money(n)}\n수수료 차감 후 수령액: {format_money(sendmoney)}',
                    ),
                    timeout=30,
                )

                if confirmed is None:
                    await ctx.send(embed=get_embed('시간 초과', '송금이 취소되었습니다.', 0xFF0000))
                    return
                if confirmed is False:
                    await ctx.send(embed=get_embed('송금 취소', '송금이 취소되었습니다.', 0xFF0000))
                    return

                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(sender_money - n), ctx.author.id))
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(receiver_money + sendmoney), muser.id))

        await ctx.send(embed=get_embed('송금 완료', f'{muser.mention}님에게 {format_money(sendmoney)}이 전달되었습니다.'))

    @commands.group(name='돈순위', aliases=['순위', '랭크', '순'], invoke_without_command=True)
    async def _money_rank(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata')
                rows = await cur.fetchall()
        ranking = sorted([[row['id'], int(row['money']) + int(row['bank'])] for row in rows], key=lambda x: x[1], reverse=True)
        embed = get_embed('알티봇 돈순위 전체 TOP 10')
        for idx, row in enumerate(ranking[:10], start=1):
            user = self.client.get_user(int(row[0]))
            name = user.name if user else str(row[0])
            embed.add_field(name=f'{idx}위 {name}', value=format_money(row[1]), inline=False)
        await ctx.send(embed=embed)

    @_money_rank.command(name='서버', aliases=['섭'])
    async def money_rank_server(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata')
                rows = await cur.fetchall()
        ranking = sorted([[row['id'], int(row['money']) + int(row['bank'])] for row in rows], key=lambda x: x[1], reverse=True)
        embed = get_embed('알티봇 돈순위 서버 TOP 10')
        count = 0
        for user_id, total in ranking:
            member = ctx.guild.get_member(int(user_id))
            if member is None:
                continue
            count += 1
            embed.add_field(name=f'{count}위 {member.name}', value=format_money(total), inline=False)
            if count >= 10:
                break
        await ctx.send(embed=embed)

    @commands.group(name='저금', invoke_without_command=True)
    async def _money_save(self, ctx, n: int):
        if n <= 0:
            raise errors.morethan1
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, bank_value = await self.get_user_money(cur, ctx.author.id)
                if money_value < n:
                    raise errors.NoMoney
                await cur.execute('UPDATE userdata SET money = %s, bank = %s WHERE id = %s', (str(money_value - n), str(bank_value + n), ctx.author.id))
        await ctx.send(embed=get_embed('저금 완료', f'{format_money(n)}을 은행에 넣었습니다.'))

    @_money_save.command(name='전체', aliases=['다', '올인', '전부', '최대'])
    async def _money_save_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, bank_value = await self.get_user_money(cur, ctx.author.id)
                await cur.execute('UPDATE userdata SET money = %s, bank = %s WHERE id = %s', ('0', str(money_value + bank_value), ctx.author.id))
        await ctx.send(embed=get_embed('저금 완료', '지갑의 모든 돈을 은행에 넣었습니다.'))

    @commands.group(name='인출', invoke_without_command=True)
    async def _money_withdraw(self, ctx, n: int):
        if n <= 0:
            raise errors.morethan1
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, bank_value = await self.get_user_money(cur, ctx.author.id)
                if bank_value < n:
                    raise errors.NoMoney
                await cur.execute('UPDATE userdata SET money = %s, bank = %s WHERE id = %s', (str(money_value + n), str(bank_value - n), ctx.author.id))
        await ctx.send(embed=get_embed('인출 완료', f'{format_money(n)}을 지갑으로 꺼냈습니다.'))

    @_money_withdraw.command(name='전체', aliases=['다', '올인'])
    async def _money_withdraw_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                money_value, bank_value = await self.get_user_money(cur, ctx.author.id)
                await cur.execute('UPDATE userdata SET money = %s, bank = %s WHERE id = %s', (str(money_value + bank_value), '0', ctx.author.id))
        await ctx.send(embed=get_embed('인출 완료', '은행의 모든 돈을 지갑으로 꺼냈습니다.'))

    @commands.command(name='은행잔고', aliases=['잔고', '은행'])
    async def bank_money(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                _, bank_value = await self.get_user_money(cur, ctx.author.id)
        await ctx.send(embed=get_embed(f'{ctx.author} 님의 은행잔고', format_money(bank_value)))


async def setup(client):
    await client.add_cog(money(client))
