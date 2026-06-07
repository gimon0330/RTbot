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

            difficulties = {
                'easy': {
                    'name': '쉬움',
                    'emoji': '😀',
                    'max_number': 20,
                    'chance': 5,
                    'reward_rate': 1.5,
                    'color': 0x66FF99,
                },
                'normal': {
                    'name': '보통',
                    'emoji': '😠',
                    'max_number': 50,
                    'chance': 6,
                    'reward_rate': 2.5,
                    'color': 0xFFCC66,
                },
                'hard': {
                    'name': '어려움',
                    'emoji': '🤬',
                    'max_number': 100,
                    'chance': 7,
                    'reward_rate': 4,
                    'color': 0xFF6666,
                },
            }

            cog = self

            class DifficultyView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30)
                    self.selected = None
                    self.message = None

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message('이 게임은 명령어를 사용한 사람만 선택할 수 있습니다.', ephemeral=True)
                        return False
                    return True

                def disable_all_buttons(self):
                    for item in self.children:
                        item.disabled = True

                async def select_difficulty(self, interaction: discord.Interaction, key: str):
                    self.selected = key
                    self.disable_all_buttons()

                    setting = difficulties[key]
                    await interaction.response.edit_message(
                        embed=get_embed(
                            f'{setting["emoji"]} {setting["name"]}',
                            f'1~{setting["max_number"]} | {setting["chance"]}번 | {setting["reward_rate"]}배',
                            setting['color']
                        ),
                        view=self
                    )
                    self.stop()

                @discord.ui.button(label='쉬움', emoji='😀', style=discord.ButtonStyle.success)
                async def easy(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.select_difficulty(interaction, 'easy')

                @discord.ui.button(label='보통', emoji='😠', style=discord.ButtonStyle.primary)
                async def normal(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.select_difficulty(interaction, 'normal')

                @discord.ui.button(label='어려움', emoji='🤬', style=discord.ButtonStyle.danger)
                async def hard(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await self.select_difficulty(interaction, 'hard')

                @discord.ui.button(label='취소', emoji='❌', style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.selected = 'cancel'
                    self.disable_all_buttons()
                    await interaction.response.edit_message(
                        embed=get_embed('취소되었습니다.', '', 0xFF0000),
                        view=self
                    )
                    self.stop()

            view = DifficultyView()
            embed = get_embed(
                '업다운 선택',
                f'베팅: {n:,}원\n\n'
                '😀 쉬움 1~20 / 5번 / 1.5배\n'
                '😠 보통 1~50 / 6번 / 2.5배\n'
                '🤬 어려움 1~100 / 7번 / 4배'
            )

            msg = await ctx.send(embed=embed, view=view)
            view.message = msg

            timed_out = await view.wait()

            if timed_out or view.selected is None:
                view.disable_all_buttons()
                await msg.edit(embed=get_embed('시간 초과', '게임이 취소되었습니다.', 0xFF0000), view=view)
                return

            if view.selected == 'cancel':
                return

            setting = difficulties[view.selected]
            max_number = setting['max_number']
            chance = setting['chance']
            reward_rate = setting['reward_rate']
            answer = randint(1, max_number)

            await ctx.send(
                embed=get_embed(
                    f'업다운 시작',
                    f'1~{max_number} | 기회 {chance}번\n'
                    '숫자를 입력하세요.',
                    setting['color']
                )
            )

            used = 0
            last_guess = None

            def number_check(message):
                if message.author != ctx.author or message.channel != ctx.channel:
                    return False

                content = message.content.strip()

                if content in ['0', 'x', 'X', '취소']:
                    return True

                try:
                    guess = int(content)
                except ValueError:
                    return False

                return 1 <= guess <= max_number

            while used < chance:
                try:
                    guess_msg = await self.client.wait_for('message', check=number_check, timeout=30)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '게임이 취소되었습니다.', 0xFF0000))
                    return

                content = guess_msg.content.strip()

                if content in ['0', 'x', 'X', '취소']:
                    await ctx.send(embed=get_embed('취소되었습니다.', '', 0xFF0000))
                    return

                guess = int(content)
                used += 1
                last_guess = guess
                remain = chance - used

                if guess == answer:
                    reward = int(n * reward_rate)

                    async with cog.pool.acquire() as conn:
                        async with conn.cursor(aiomysql.DictCursor) as cur:
                            await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                            row = await cur.fetchone()
                            current_money = int(row['money'])
                            await cur.execute(
                                'UPDATE userdata SET money = %s WHERE id = %s',
                                (str(current_money + reward), ctx.author.id)
                            )

                    await ctx.send(
                        embed=get_embed(
                            '정답!',
                            f'{answer} | {used}/{chance}\n'
                            f'+{reward:,}원',
                            0x00FF00
                        )
                    )
                    return

                if remain <= 0:
                    break

                if guess < answer:
                    hint = '⬆️ UP'
                else:
                    hint = '⬇️ DOWN'

                await ctx.send(
                    embed=get_embed(
                        hint,
                        f'{guess} 아님 | 남은 기회 {remain}번'
                    )
                )

            async with cog.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                    row = await cur.fetchone()
                    current_money = int(row['money'])
                    await cur.execute(
                        'UPDATE userdata SET money = %s WHERE id = %s',
                        (str(current_money - n), ctx.author.id)
                    )

            await ctx.send(
                embed=get_embed(
                    '실패',
                    f'정답 {answer}\n'
                    f'-{n:,}원',
                    0xFF0000
                )
            )

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
