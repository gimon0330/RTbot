import asyncio
import typing
from random import randint

import aiomysql
import discord
from discord.ext import commands

from utils import errors
from exts.minigame import get_embed


class UpdownReplacement(commands.Cog):
    """숫자맞추기 명령어의 안전한 대체 구현."""

    def __init__(self, client):
        self.client = client
        self.pool = client.pool

    def minigame_cog(self):
        return self.client.get_cog('minigame')

    @commands.command(name='숫자맞추기', aliases=['숫맞', '업다운', '업다운게임'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def updown(self, ctx, n: typing.Union[str, int, None] = None):
        minigame = self.minigame_cog()
        if minigame is None:
            await ctx.send(embed=get_embed('오류', '미니게임 모듈을 찾을 수 없습니다.', 0xFF0000))
            return

        money = await minigame.start_game(ctx.author.id)
        try:
            if not n:
                await ctx.send(
                    embed=get_embed(
                        '금액 입력',
                        '걸 금액을 입력해주세요. `0`, `x`, `X`를 입력하면 시작 전에 취소할 수 있습니다.'
                    )
                )

                def amount_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=amount_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '게임을 시작하지 않았습니다.', 0xFF0000))
                    return

                n = msg.content.strip()
                if n in ['0', 'X', 'x', '취소']:
                    await ctx.send(embed=get_embed('취소되었습니다.', '게임을 시작하지 않아 돈은 차감되지 않았습니다.', 0xFF0000))
                    return

            try:
                n = int(n)
            except (TypeError, ValueError):
                if n in ['올인', '전부', '전체', '최대']:
                    n = money
                else:
                    raise errors.morethan1

            if n <= 0:
                raise errors.morethan1
            if n > money:
                raise errors.NoMoney

            class StartView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30)
                    self.started = None

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user.id != ctx.author.id:
                        await interaction.response.send_message(
                            '이 게임은 명령어를 사용한 사람만 진행할 수 있습니다.',
                            ephemeral=True,
                        )
                        return False
                    return True

                def disable_all_buttons(self):
                    for item in self.children:
                        item.disabled = True

                @discord.ui.button(label='게임 시작', emoji='🎮', style=discord.ButtonStyle.success)
                async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.started = True
                    self.disable_all_buttons()
                    await interaction.response.edit_message(view=self)
                    self.stop()

                @discord.ui.button(label='취소', emoji='❌', style=discord.ButtonStyle.secondary)
                async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.started = False
                    self.disable_all_buttons()
                    await interaction.response.edit_message(
                        embed=get_embed('취소되었습니다.', '게임을 시작하지 않아 돈은 차감되지 않았습니다.', 0xFF0000),
                        view=self,
                    )
                    self.stop()

            view = StartView()
            start_message = await ctx.send(
                embed=get_embed(
                    '숫자맞추기 시작 확인',
                    f'베팅 금액: {n:,}원\n'
                    '범위: 1~20\n'
                    '기회: 4번\n\n'
                    '1번째 정답: 4배 지급\n'
                    '2번째 정답: 3배 지급\n'
                    '3번째 정답: 2배 지급\n'
                    '4번째 정답: 1배 지급\n\n'
                    '⚠️ 게임 시작 버튼을 누르는 즉시 베팅 금액이 차감됩니다.\n'
                    '그 뒤에는 취소, 시간 초과, 오류 등 어떤 방식으로 중지해도 환급되지 않습니다.'
                ),
                view=view,
            )

            timed_out = await view.wait()
            if timed_out or view.started is None:
                view.disable_all_buttons()
                await start_message.edit(
                    embed=get_embed('시간 초과', '게임을 시작하지 않아 돈은 차감되지 않았습니다.', 0xFF0000),
                    view=view,
                )
                return
            if view.started is False:
                return

            # 게임 시작 시점에 베팅금을 먼저 차감한다.
            async with self.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                    row = await cur.fetchone()
                    current_money = int(row['money'])

                    if current_money < n:
                        await ctx.send(embed=get_embed('잔액 부족', '게임 시작 전에 잔액이 변경되어 시작할 수 없습니다.', 0xFF0000))
                        return

                    await cur.execute(
                        'UPDATE userdata SET money = %s WHERE id = %s',
                        (str(current_money - n), ctx.author.id),
                    )

            answer = randint(1, 20)
            payout_rates = {1: 4, 2: 3, 3: 2, 4: 1}

            await ctx.send(
                embed=get_embed(
                    '업다운 시작',
                    f'{n:,}원이 차감되었습니다.\n'
                    '1~20 사이의 숫자를 입력하세요. 남은 기회는 4번입니다.\n'
                    '`0`, `x`, `X`, `취소`로 중지할 수 있지만 베팅금은 환급되지 않습니다.'
                )
            )

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

                return 1 <= guess <= 20

            for attempt in range(1, 5):
                try:
                    guess_msg = await self.client.wait_for('message', check=number_check, timeout=30)
                except asyncio.TimeoutError:
                    await ctx.send(
                        embed=get_embed(
                            '시간 초과',
                            f'게임이 종료되었습니다. 베팅금 {n:,}원은 환급되지 않습니다.\n정답은 {answer}였습니다.',
                            0xFF0000,
                        )
                    )
                    return

                content = guess_msg.content.strip()
                if content in ['0', 'x', 'X', '취소']:
                    await ctx.send(
                        embed=get_embed(
                            '게임 중지',
                            f'게임이 종료되었습니다. 베팅금 {n:,}원은 환급되지 않습니다.\n정답은 {answer}였습니다.',
                            0xFF0000,
                        )
                    )
                    return

                guess = int(content)
                if guess == answer:
                    multiplier = payout_rates[attempt]
                    payout = n * multiplier

                    async with self.pool.acquire() as conn:
                        async with conn.cursor(aiomysql.DictCursor) as cur:
                            await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                            row = await cur.fetchone()
                            current_money = int(row['money'])
                            await cur.execute(
                                'UPDATE userdata SET money = %s WHERE id = %s',
                                (str(current_money + payout), ctx.author.id),
                            )

                    await ctx.send(
                        embed=get_embed(
                            '정답!',
                            f'정답은 {answer}입니다.\n'
                            f'{attempt}번째 시도 성공 · {multiplier}배 지급\n'
                            f'+{payout:,}원',
                            0x00FF00,
                        )
                    )
                    return

                remaining = 4 - attempt
                if remaining == 0:
                    break

                hint = '⬆️ UP' if guess < answer else '⬇️ DOWN'
                await ctx.send(
                    embed=get_embed(
                        hint,
                        f'{guess}은(는) 정답이 아닙니다. 남은 기회 {remaining}번'
                    )
                )

            await ctx.send(
                embed=get_embed(
                    '실패',
                    f'4번 안에 맞추지 못했습니다.\n정답은 {answer}였습니다.\n베팅금 {n:,}원은 환급되지 않습니다.',
                    0xFF0000,
                )
            )
        finally:
            minigame.end_game(ctx.author.id)


async def setup(client):
    # 기존 minigame.py의 숫자맞추기 명령어와 별칭을 제거한 뒤 대체 명령어를 등록한다.
    client.remove_command('숫자맞추기')
    await client.add_cog(UpdownReplacement(client))
