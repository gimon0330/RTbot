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
        
    @commands.group(name='가위바위보', aliases=['가위바위보게임', 'rsp'], invoke_without_command=True)
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rsp(self, ctx, n: typing.Union[str, int, None] = None):
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

            choices = ['가위', '바위', '보']
            emojis = {
                '가위': '✌️',
                '바위': '✊',
                '보': '✋',
            }

            win_table = {
                '가위': '보',
                '바위': '가위',
                '보': '바위',
            }

            cog = self

            class RSPView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30)
                    self.finished = False
                    self.message = None

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message('이 게임은 명령어를 사용한 사람만 진행할 수 있습니다.', ephemeral=True)
                        return False
                    return True

                def disable_all_buttons(self):
                    for item in self.children:
                        item.disabled = True

                async def play(self, interaction: discord.Interaction, user_choice: str):
                    if self.finished:
                        return

                    self.finished = True
                    bot_choice = random.choice(choices)

                    if user_choice == bot_choice:
                        delta = 0
                        result_title = '무승부'
                        result_desc = '비겼습니다. 돈은 변하지 않습니다.'
                        color = 0xCCFFFF
                    elif win_table[user_choice] == bot_choice:
                        delta = n
                        result_title = '승리!'
                        result_desc = f'{n:,}원을 획득했습니다.'
                        color = 0x00FF00
                    else:
                        delta = -n
                        result_title = '패배...'
                        result_desc = f'{n:,}원을 잃었습니다.'
                        color = 0xFF0000

                    async with cog.pool.acquire() as conn:
                        async with conn.cursor(aiomysql.DictCursor) as cur:
                            if delta != 0:
                                await cur.execute('SELECT money FROM userdata WHERE id = %s', (ctx.author.id,))
                                row = await cur.fetchone()
                                current_money = int(row['money'])
                                await cur.execute(
                                    'UPDATE userdata SET money = %s WHERE id = %s',
                                    (str(current_money + delta), ctx.author.id)
                                )

                    self.disable_all_buttons()

                    embed = get_embed(
                        result_title,
                        f'당신: {emojis[user_choice]} {user_choice}\n'
                        f'알티: {emojis[bot_choice]} {bot_choice}\n\n'
                        f'{result_desc}',
                        color
                    )

                    await interaction.response.edit_message(embed=embed, view=self)
                    self.stop()

                @discord.ui.button(label='가위', emoji='✌️', style=discord.ButtonStyle.primary)
                async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.play(interaction, '가위')

                @discord.ui.button(label='바위', emoji='✊', style=discord.ButtonStyle.primary)
                async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.play(interaction, '바위')

                @discord.ui.button(label='보', emoji='✋', style=discord.ButtonStyle.primary)
                async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.play(interaction, '보')

            view = RSPView()
            embed = get_embed(
                '가위바위보',
                f'금액: {n:,}원\n\n'
                '이기면 건 돈만큼 추가로 얻고,\n'
                '지면 건 돈만큼 잃고,\n'
                '비기면 아무 일도 일어나지 않습니다.\n\n'
                '아래 버튼 중 하나를 선택해주세요.'
            )

            msg = await ctx.send(embed=embed, view=view)
            view.message = msg

            timed_out = await view.wait()
            if timed_out and not view.finished:
                view.disable_all_buttons()
                await msg.edit(embed=get_embed('시간 초과', '가위바위보가 취소되었습니다.', 0xFF0000), view=view)

        finally:
            self.end_game(ctx.author.id)

    
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
                embed=get_embed(
                    '슬롯 확인',
                    f'금액: {n:,}원\n'
                    '🔔🔔🔔 100배 / ⭐⭐⭐ 50배 / 🍒🍒🍒 20배 / 🍈🍈🍈 8배\n'
                    '같은 심볼 2개 1.5배 / 전부 다름 -1배 / 💩 2개 이상 -2배'
                ),
                timeout=30,
            )
            if confirmed is None:
                await ctx.send(embed=get_embed('시간 초과', '슬롯이 취소되었습니다.', 0xFF0000))
                return
            if confirmed is False:
                await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                return

            symbols = ['🔔', '⭐', '🍒', '🍈', '❌', '💩']
            slot = random.choices(list(range(0, 6)), weights=[3, 7, 20, 25, 25, 20], k=3)

            msg = await ctx.send('❓ ❓ ❓')
            await asyncio.sleep(1)
            await msg.edit(content=f'❓ ❓ {symbols[slot[0]]}')
            await asyncio.sleep(1)
            await msg.edit(content=f'❓ {symbols[slot[1]]} {symbols[slot[0]]}')
            await asyncio.sleep(1)
            await msg.edit(content=f'{symbols[slot[2]]} {symbols[slot[1]]} {symbols[slot[0]]}')

            counts = {symbol: slot.count(i) for i, symbol in enumerate(symbols)}

            if counts['🔔'] == 3:
                multiplier = 100
                reason = '🔔 3개 대박!'
            elif counts['⭐'] == 3:
                multiplier = 50
                reason = '⭐ 3개 당첨!'
            elif counts['🍒'] == 3:
                multiplier = 20
                reason = '🍒 3개 당첨!'
            elif counts['🍈'] == 3:
                multiplier = 8
                reason = '🍈 3개 당첨!'
            elif counts['💩'] >= 2:
                multiplier = -2
                reason = '💩 2개 이상 손실'
            elif counts['❌'] == 3:
                multiplier = -2
                reason = '❌ 3개 손실'
            elif max(counts.values()) == 2:
                multiplier = 1.5
                reason = '같은 심볼 2개 소액 당첨'
            else:
                multiplier = -1
                reason = '꽝'

            delta = int(n * multiplier)

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
            await ctx.send(embed=get_embed('슬롯 결과', f'{reason}\n총 배수: {multiplier}배\n{result}'))
        finally:
            self.end_game(ctx.author.id)


async def setup(client):
    await client.add_cog(minigame(client))
