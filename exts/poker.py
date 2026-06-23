import asyncio
import random
import typing
from collections import Counter

import aiomysql
import discord
from discord.ext import commands

from utils import checks, errors
from utils.user_state import begin_interaction, end_interaction


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


def format_money(value):
    return f'{int(value):,}원'


RANK_LABELS = {
    2: '2',
    3: '3',
    4: '4',
    5: '5',
    6: '6',
    7: '7',
    8: '8',
    9: '9',
    10: '10',
    11: 'J',
    12: 'Q',
    13: 'K',
    14: 'A',
}

SUITS = ['♠️', '♥️', '♦️', '♣️']

# 배수는 기존 포커의 순이익 배수를 의미한다.
# 게임 시작 시 베팅금을 먼저 차감하므로 당첨 시에는 원금까지 함께 돌려준다.
HAND_MULTIPLIERS = {
    '노페어': -1,
    '원페어': 1,
    '투페어': 2,
    '트리플': 3,
    '스트레이트': 4,
    '플러쉬': 4,
    '풀하우스': 5,
    '포카드': 8,
    '스트레이트 플러쉬': 10,
}


def make_deck():
    return [(rank, suit) for suit in SUITS for rank in range(2, 15)]


def format_card(card):
    rank, suit = card
    return f'{suit}{RANK_LABELS[rank]}'


def format_hand(hand, selected=None):
    selected = selected or set()
    lines = []

    for idx, card in enumerate(hand):
        marker = ' ✅' if idx in selected else ''
        lines.append(f'`{idx + 1}` {format_card(card)}{marker}')

    return '\n'.join(lines)


def is_straight(ranks):
    unique_ranks = sorted(set(ranks))

    if len(unique_ranks) != 5:
        return False

    # A, 2, 3, 4, 5도 스트레이트로 인정한다.
    if unique_ranks == [2, 3, 4, 5, 14]:
        return True

    return unique_ranks[-1] - unique_ranks[0] == 4


def evaluate_hand(hand):
    ranks = [rank for rank, _ in hand]
    suits = [suit for _, suit in hand]
    rank_counts = Counter(ranks)
    count_values = sorted(rank_counts.values(), reverse=True)
    flush = len(set(suits)) == 1
    straight = is_straight(ranks)

    if straight and flush:
        hand_name = '스트레이트 플러쉬'
    elif count_values == [4, 1]:
        hand_name = '포카드'
    elif count_values == [3, 2]:
        hand_name = '풀하우스'
    elif flush:
        hand_name = '플러쉬'
    elif straight:
        hand_name = '스트레이트'
    elif count_values == [3, 1, 1]:
        hand_name = '트리플'
    elif count_values == [2, 2, 1]:
        hand_name = '투페어'
    elif count_values == [2, 1, 1, 1]:
        hand_name = '원페어'
    else:
        hand_name = '노페어'

    return hand_name, HAND_MULTIPLIERS[hand_name]


class PokerStartView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.started = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True

        await interaction.response.send_message(
            '이 게임은 명령어를 실행한 사람만 진행할 수 있습니다.',
            ephemeral=True,
        )
        return False

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label='게임 시작', emoji='🃏', style=discord.ButtonStyle.success)
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
            embed=get_embed(
                '취소되었습니다.',
                '카드를 받기 전 취소하여 돈은 차감되지 않았습니다.',
                0xFF0000,
            ),
            view=self,
        )
        self.stop()


class PokerCardButton(discord.ui.Button):
    def __init__(self, index):
        super().__init__(
            label=str(index + 1),
            style=discord.ButtonStyle.secondary,
            row=0,
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.toggle_card(interaction, self.index)


class PokerDrawButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='선택한 카드 교체',
            emoji='🔄',
            style=discord.ButtonStyle.primary,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.finish_game(interaction, change_selected=True)


class PokerStandButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='그대로 승부',
            emoji='🃏',
            style=discord.ButtonStyle.success,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.finish_game(interaction, change_selected=False)


class PokerCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label='게임 포기',
            emoji='❌',
            style=discord.ButtonStyle.danger,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.cancel_game(interaction)


class PokerView(discord.ui.View):
    def __init__(self, cog, ctx, bet, hand, deck):
        super().__init__(timeout=45)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.hand = hand
        self.deck = deck
        self.selected = set()
        self.finished = False

        for idx in range(5):
            self.add_item(PokerCardButton(idx))

        self.add_item(PokerDrawButton())
        self.add_item(PokerStandButton())
        self.add_item(PokerCancelButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True

        await interaction.response.send_message(
            '이 게임은 명령어를 실행한 사람만 진행할 수 있습니다.',
            ephemeral=True,
        )
        return False

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    def refresh_card_buttons(self):
        for item in self.children:
            if isinstance(item, PokerCardButton):
                item.style = (
                    discord.ButtonStyle.success
                    if item.index in self.selected
                    else discord.ButtonStyle.secondary
                )

    def select_embed(self):
        embed = get_embed(
            '포커',
            f'베팅 금액: {format_money(self.bet)} (차감 완료)\n\n'
            f'{format_hand(self.hand, self.selected)}\n\n'
            '교체할 카드를 버튼으로 선택한 뒤 `선택한 카드 교체`를 누르세요.\n'
            '카드를 바꾸지 않으려면 `그대로 승부`를 누르면 됩니다.\n\n'
            '⚠️ 패를 받은 뒤 포기하거나 시간이 초과되어도 베팅금은 환급되지 않습니다.',
        )

        embed.add_field(
            name='순이익 배당표',
            value=(
                '노페어: -1배\n'
                '원페어: +1배\n'
                '투페어: +2배\n'
                '트리플: +3배\n'
                '스트레이트: +4배\n'
                '플러쉬: +4배\n'
                '풀하우스: +5배\n'
                '포카드: +8배\n'
                '스트레이트 플러쉬: +10배'
            ),
            inline=False,
        )
        return embed

    def result_embed(self, hand_name, multiplier, profit, new_money, changed_count):
        if profit > 0:
            result_text = f'순이익 {format_money(profit)}을 획득했습니다.'
            color = 0x00FF00
        elif profit == 0:
            result_text = '베팅금만 돌려받았습니다.'
            color = 0xCCFFFF
        else:
            result_text = f'{format_money(abs(profit))}을 잃었습니다.'
            color = 0xFF0000

        return get_embed(
            '포커 결과',
            f'{format_hand(self.hand)}\n\n'
            f'족보: **{hand_name}**\n'
            f'교체한 카드: **{changed_count}장**\n'
            f'순이익 배수: **{multiplier:+}배**\n'
            f'{result_text}\n\n'
            f'현재 지갑: **{format_money(new_money)}**',
            color,
        )

    async def toggle_card(self, interaction: discord.Interaction, index: int):
        if self.finished:
            return

        if index in self.selected:
            self.selected.remove(index)
        else:
            self.selected.add(index)

        self.refresh_card_buttons()
        await interaction.response.edit_message(embed=self.select_embed(), view=self)

    def replace_selected_cards(self):
        selected_indexes = sorted(self.selected)
        if not selected_indexes:
            return 0

        # 처음 받은 다섯 장은 버린 카드까지 포함해 다시 뽑히지 않는다.
        remaining_deck = [card for card in self.deck if card not in self.hand]
        new_cards = random.sample(remaining_deck, len(selected_indexes))

        for idx, new_card in zip(selected_indexes, new_cards):
            self.hand[idx] = new_card

        return len(selected_indexes)

    async def finish_game(self, interaction: discord.Interaction, change_selected: bool):
        if self.finished:
            return

        self.finished = True
        await interaction.response.defer()

        changed_count = self.replace_selected_cards() if change_selected else 0
        hand_name, multiplier = evaluate_hand(self.hand)

        if multiplier < 0:
            # 베팅금은 시작할 때 이미 차감되었다.
            payout = 0
            profit = -self.bet
        else:
            # 기존 게임의 순이익 배수를 유지하기 위해 원금 + 순이익을 지급한다.
            payout = self.bet * (multiplier + 1)
            profit = self.bet * multiplier

        new_money = await self.cog.add_payout(self.ctx.author.id, payout)
        self.disable_all_buttons()

        await interaction.edit_original_response(
            embed=self.result_embed(hand_name, multiplier, profit, new_money, changed_count),
            view=self,
        )
        self.stop()

    async def cancel_game(self, interaction: discord.Interaction):
        if self.finished:
            return

        self.finished = True
        self.disable_all_buttons()
        current_money = await self.cog.get_money(self.ctx.author.id)

        await interaction.response.edit_message(
            embed=get_embed(
                '게임 포기',
                f'포커 게임을 포기했습니다.\n'
                f'베팅금 {format_money(self.bet)}은 환급되지 않습니다.\n'
                f'현재 지갑: {format_money(current_money)}',
                0xFF0000,
            ),
            view=self,
        )
        self.stop()


class poker(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)
        self.fallback_gaming_users = set()

        for command in self.get_commands():
            command.add_check(self.checks.registered)
            command.add_check(self.checks.blacklist)

    def minigame_cog(self):
        return self.client.get_cog('minigame')

    async def start_game(self, uid: int):
        minigame = self.minigame_cog()
        if minigame is not None:
            return await minigame.start_game(uid)

        if uid in self.fallback_gaming_users:
            raise errors.playinggame

        self.fallback_gaming_users.add(uid)
        return await self.get_money(uid)

    def end_game(self, uid: int):
        minigame = self.minigame_cog()
        if minigame is not None:
            minigame.end_game(uid)
        self.fallback_gaming_users.discard(uid)

    async def get_money(self, uid: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', uid)
                row = await cur.fetchone()

        if row is None:
            raise errors.NotRegistered
        return int(row['money'])

    async def reserve_bet(self, uid: int, bet: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', uid)
                row = await cur.fetchone()

                if row is None:
                    raise errors.NotRegistered

                current_money = int(row['money'])
                if current_money < bet:
                    return None

                new_money = current_money - bet
                await cur.execute(
                    'UPDATE userdata SET money = %s WHERE id = %s',
                    (str(new_money), uid),
                )
                return new_money

    async def add_payout(self, uid: int, payout: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', uid)
                row = await cur.fetchone()

                if row is None:
                    raise errors.NotRegistered

                new_money = int(row['money']) + int(payout)
                await cur.execute(
                    'UPDATE userdata SET money = %s WHERE id = %s',
                    (str(new_money), uid),
                )
                return new_money

    @commands.group(name='포커', aliases=['poker', '드로우포커'], invoke_without_command=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def poker_game(self, ctx, n: typing.Union[str, int, None] = None):
        if not begin_interaction(self.client, ctx.author.id, '포커 게임'):
            raise errors.ActiveInteraction('진행 중인 작업')

        game_started = False
        try:
            money = await self.start_game(ctx.author.id)
            game_started = True

            if not n:
                await ctx.send(
                    embed=get_embed(
                        '금액 입력',
                        '걸 금액을 입력해주세요. `0`, `x`, `X`를 입력하면 시작 전에 취소됩니다.',
                    )
                )

                def message_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=message_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '게임을 시작하지 않았습니다.', 0xFF0000))
                    return

                n = msg.content.strip()
                if n in ['0', 'X', 'x', '취소']:
                    await ctx.send(embed=get_embed('취소되었습니다.', '돈은 차감되지 않았습니다.', 0xFF0000))
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

            start_view = PokerStartView(ctx.author.id)
            start_message = await ctx.send(
                embed=get_embed(
                    '포커 시작 확인',
                    f'베팅 금액: {format_money(n)}\n\n'
                    '게임 시작 버튼을 누르면 베팅금이 즉시 차감되고 카드 5장을 받습니다.\n'
                    '그 이후에는 게임 포기, 시간 초과, 봇 재시작 등 어떤 이유로 종료되어도 환급되지 않습니다.\n\n'
                    '좋은 패가 나올 때까지 취소를 반복하는 악용을 막기 위한 규칙입니다.',
                ),
                view=start_view,
            )

            timed_out = await start_view.wait()
            if timed_out or start_view.started is None:
                start_view.disable_all_buttons()
                await start_message.edit(
                    embed=get_embed(
                        '시간 초과',
                        '카드를 받기 전 종료되어 돈은 차감되지 않았습니다.',
                        0xFF0000,
                    ),
                    view=start_view,
                )
                return

            if start_view.started is False:
                return

            remaining_money = await self.reserve_bet(ctx.author.id, n)
            if remaining_money is None:
                await start_message.edit(
                    embed=get_embed(
                        '잔액 부족',
                        '확인하는 동안 잔액이 변경되어 포커를 시작할 수 없습니다.',
                        0xFF0000,
                    ),
                    view=start_view,
                )
                return

            deck = make_deck()
            hand = random.sample(deck, 5)
            view = PokerView(
                cog=self,
                ctx=ctx,
                bet=n,
                hand=hand,
                deck=deck,
            )

            game_message = await ctx.send(embed=view.select_embed(), view=view)
            timed_out = await view.wait()

            if timed_out and not view.finished:
                view.finished = True
                view.disable_all_buttons()
                await game_message.edit(
                    embed=get_embed(
                        '시간 초과',
                        f'포커 게임이 종료되었습니다.\n'
                        f'베팅금 {format_money(n)}은 환급되지 않습니다.\n'
                        f'현재 지갑: {format_money(await self.get_money(ctx.author.id))}',
                        0xFF0000,
                    ),
                    view=view,
                )
        finally:
            if game_started:
                self.end_game(ctx.author.id)
            end_interaction(self.client, ctx.author.id)


async def setup(client):
    await client.add_cog(poker(client))
