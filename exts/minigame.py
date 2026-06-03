import asyncio
import random
import typing
from random import randint

import aiomysql
import discord
from discord.ext import commands

from utils import errors, checks
from utils.views import ask_confirm


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


class minigame(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)
        self.gaming_users = set()

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.blacklist)

    async def start_game(self, uid: int):
        if uid in self.gaming_users:
            raise errors.playinggame
        self.gaming_users.add(uid)
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', uid)
                row = await cur.fetchone()
                return int(row['money'])

    def end_game(self, uid: int):
        self.gaming_users.discard(uid)

    @commands.group(name='가위바위보', invoke_without_command=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rsp(self, ctx, n: typing.Union[str, None] = None):
        await ctx.send(embed=get_embed('이 기능은 잠시 비활성화되었습니다.', '현재 재작성 과정에 있어 이 명령어는 임시 비활성화 상태입니다.', 0xFF0000))

    @commands.command(name='숫자맞추기', aliases=['숫맞', '업다운', '업다운게임'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def updown(self, ctx, n: typing.Union[str, int, None] = None):
        money = await self.start_game(ctx.author.id)
        try:
            if not n:
                await ctx.send(embed=get_embed('금액 입력', '걸 금액을 입력해주세요. `0`, `x`, `X`를 입력하면 취소됩니다.'))

                def message_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=message_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '', 0xFF0000))
                    return

                n = msg.content
                if n in ['0', 'X', 'x']:
                    await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                    return

            try:
                n = int(n)
            except Exception:
                if n in ['올인', '전부', '전체', '최대']:
                    n = money
                else:
                    raise errors.morethan1

            if n <= 0:
                raise errors.morethan1
            if n > money:
                raise errors.NoMoney

            embed = get_embed('숫자맞추기 난이도', '실패 시 건 돈은 사라집니다.')
            embed.add_field(name='😀 쉬움', value='1~10, 보상 1~2배')
            embed.add_field(name='😠 보통', value='1~20, 보상 2~4배')
            embed.add_field(name='🤬 어려움', value='1~30, 보상 3~6배')
            embed.set_footer(text='반응으로 난이도를 골라주세요. ❌는 취소입니다.')
            msg = await ctx.send(embed=embed)

            choices = ['😀', '😠', '🤬', '❌']
            for emoji in choices:
                await msg.add_reaction(emoji)

            def reaction_check(reaction, user):
                return user == ctx.author and msg.id == reaction.message.id and str(reaction.emoji) in choices

            try:
                reaction, user = await self.client.wait_for('reaction_add', check=reaction_check, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(embed=get_embed('시간 초과', '', 0xFF0000))
                return

            emoji = str(reaction.emoji)
            if emoji == '😀':
                number = randint(1, 10)
                level = 1
            elif emoji == '😠':
                number = randint(1, 20)
                level = 2
            elif emoji == '🤬':
                number = randint(1, 30)
                level = 3
            else:
                await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                return

            await ctx.send(embed=get_embed('숫자를 입력해주세요.'))

            def number_check(message):
                if message.author != ctx.author or message.channel != ctx.channel:
                    return False
                try:
                    int(message.content)
                    return True
                except ValueError:
                    return False

            try:
                answer = await self.client.wait_for('message', check=number_check, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(embed=get_embed('시간 초과', '', 0xFF0000))
                return

            diff = abs(int(answer.content) - number)
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                    row = await cur.fetchone()
                    current_money = int(row['money'])
                    await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(current_money - n), ctx.author.id))

                    if diff == 0:
                        reward = n * level * 2
                        message = f'정확합니다! 정답은 {number}입니다. {reward:,}원 지급!'
                    elif diff == 1:
                        reward = int(n * level * 1.5)
                        message = f'1 차이입니다! 정답은 {number}입니다. {reward:,}원 지급!'
                    elif diff == 2:
                        reward = n * level
                        message = f'2 차이입니다! 정답은 {number}입니다. {reward:,}원 지급!'
                    else:
                        reward = 0
                        message = f'실패했습니다. 정답은 {number}입니다.'

                    if reward:
                        await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(current_money - n + reward), ctx.author.id))

            await ctx.send(embed=get_embed('숫자맞추기 결과', message))
        finally:
            self.end_game(ctx.author.id)

    @commands.group(name='슬롯')
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def slot(self, ctx, n: typing.Union[str, int, None] = None):
        money = await self.start_game(ctx.author.id)
        try:
            if not n:
                await ctx.send(embed=get_embed('금액 입력', '걸 금액을 입력해주세요. `0`, `x`, `X`를 입력하면 취소됩니다.'))

                def message_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=message_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '', 0xFF0000))
                    return
                n = msg.content
                if n in ['0', 'X', 'x']:
                    await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                    return

            try:
                n = int(n)
            except Exception:
                if n in ['올인', '전부', '전체', '최대']:
                    n = money // 200
                else:
                    raise errors.morethan1

            if n <= 0:
                raise errors.morethan1
            if n > money:
                raise errors.NoMoney
            if money < 2000:
                await ctx.send(embed=get_embed('최소 자산 부족', f'최소 2000원이 필요합니다. 현재 금액: {money:,}원', 0xFF0000))
                return
            if n > money // 200:
                await ctx.send(embed=get_embed('금액 초과', f'현재 금액의 200분의 1 이상 사용할 수 없습니다. 최대 금액: {money // 200:,}원', 0xFF0000))
                return

            confirmed, _ = await ask_confirm(
                ctx,
                embed=get_embed('슬롯 확인', f'금액: {n:,}원\n🔔 10배 / ⭐ 6배 / 🍒 2배 / 🍈 0배 / ❌ -1배 / 💩 -2배'),
                timeout=30,
            )
            if confirmed is None:
                await ctx.send(embed=get_embed('시간 초과', '슬롯이 취소되었습니다.', 0xFF0000))
                return
            if confirmed is False:
                await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                return

            symbols = ['🔔', '⭐', '🍒', '🍈', '❌', '💩']
            multipliers = [10, 6, 2, 0, -1, -2]
            slot = random.choices(list(range(0, 6)), weights=[20, 15, 20, 5, 20, 20], k=3)

            msg = await ctx.send('❓ ❓ ❓')
            await asyncio.sleep(1)
            await msg.edit(content=f'❓ ❓ {symbols[slot[0]]}')
            await asyncio.sleep(1)
            await msg.edit(content=f'❓ {symbols[slot[1]]} {symbols[slot[0]]}')
            await asyncio.sleep(1)
            await msg.edit(content=f'{symbols[slot[2]]} {symbols[slot[1]]} {symbols[slot[0]]}')

            multiplier = 1
            for item in slot:
                multiplier *= multipliers[item]
            delta = n * multiplier

            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                    row = await cur.fetchone()
                    current_money = int(row['money'])
                    await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(current_money + delta), ctx.author.id))

            if delta > 0:
                result = f'{delta:,}원을 획득했습니다.'
            elif delta == 0:
                result = '획득도 손실도 없습니다.'
            else:
                result = f'{abs(delta):,}원을 잃었습니다.'
            await ctx.send(embed=get_embed('슬롯 결과', f'총 배수: {multiplier}배\n{result}'))
        finally:
            self.end_game(ctx.author.id)


async def setup(client):
    await client.add_cog(minigame(client))
