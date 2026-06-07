import asyncio
import random
import typing
from collections import Counter

import aiomysql
import discord
from discord.ext import commands

from utils import errors, checks


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

    # A, 2, 3, 4, 5
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
        return '스트레이트 플러쉬', 10

    if count_values == [4, 1]:
        return '포카드', 8

    if count_values == [3, 2]:
        return '풀하우스', 5

    if flush:
        return '플러쉬', 4

    if straight:
        return '스트레이트', 4

    if count_values == [3, 1, 1]:
        return '트리플', 3

    if count_values == [2, 2, 1]:
        return '투페어', 2

    if count_values == [2, 1, 1, 1]:
        return '원페어', 1

    return '노페어', -1


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
            label='취소',
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
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                '이 게임은 명령어를 실행한 사람만 진행할 수 있습니다.',
                ephemeral=True,
            )
            return False

        return True

    def disable_all_buttons(self):
        for item in self.children:
            item.disabled = True

    def refresh_card_buttons(self):
        for item in self.children:
            if isinstance(item, PokerCardButton):
                if item.index in self.selected:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary

    def select_embed(self):
        embed = get_embed(
            '포커',
            f'베팅 금액: {format_money(self.bet)}\n\n'
            f'{format_hand(self.hand, self.selected)}\n\n'
            '교체할 카드를 버튼으로 선택한 뒤 `선택한 카드 교체`를 누르세요.\n'
            '카드를 바꾸지 않으려면 `그대로 승부`를 누르면 됩니다.',
        )

        embed.add_field(
            name='배당표',
            value=(
                '노페어: -1배\n'
                '원페어: 1배\n'
                '투페어: 2배\n'
                '트리플: 3배\n'
                '스트레이트: 4배\n'
                '플러쉬: 4배\n'
                '풀하우스: 5배\n'
                '포카드: 8배\n'
                '스트레이트 플러쉬: 10배'
            ),
            inline=False,
        )

        return embed

    def result_embed(self, hand_name, multiplier, delta, new_money, changed_count):
        if delta > 0:
            result_text = f'{format_money(delta)}을 획득했습니다.'
            color = 0x00FF00
        else:
            result_text = f'{format_money(abs(delta))}을 잃었습니다.'
            color = 0xFF0000

        embed = get_embed(
            '포커 결과',
            f'{format_hand(self.hand)}\n\n'
            f'족보: **{hand_name}**\n'
            f'교체한 카드: **{changed_count}장**\n'
            f'배수: **{multiplier}배**\n'
            f'{result_text}\n\n'
            f'현재 지갑: **{format_money(new_money)}**',
            color,
        )

        return embed

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

        remain_deck = [card for card in self.deck if card not in self.hand]
        new_cards = random.sample(remain_deck, len(selected_indexes))

        for idx, new_card in zip(selected_indexes, new_cards):
            self.hand[idx] = new_card

        return len(selected_indexes)

    async def finish_game(self, interaction: discord.Interaction, change_selected: bool):
        if self.finished:
            return

        self.finished = True
        await interaction.response.defer()

        changed_count = 0
        if change_selected:
            changed_count = self.replace_selected_cards()

        hand_name, multiplier = evaluate_hand(self.hand)

        if multiplier < 0:
            delta = -self.bet
        else:
            delta = self.bet * multiplier

        new_money = await self.cog.apply_money_delta(self.ctx.author.id, delta)

        self.disable_all_buttons()

        await interaction.edit_original_response(
            embed=self.result_embed(hand_name, multiplier, delta, new_money, changed_count),
            view=self,
        )

        self.stop()

    async def cancel_game(self, interaction: discord.Interaction):
        if self.finished:
            return

        self.finished = True
        self.disable_all_buttons()

        await interaction.response.edit_message(
            embed=get_embed('취소되었습니다.', '포커 게임이 취소되었습니다.', 0xFF0000),
            view=self,
        )

        self.stop()


class poker(commands.Cog):
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

    async def apply_money_delta(self, uid: int, delta: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', uid)
                row = await cur.fetchone()

                current_money = int(row['money'])
                new_money = max(0, current_money + int(delta))

                await cur.execute(
                    'UPDATE userdata SET money = %s WHERE id = %s',
                    (str(new_money), uid),
                )

                return new_money

    @commands.group(name='포커', aliases=['poker', '드로우포커'], invoke_without_command=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def poker_game(self, ctx, n: typing.Union[str, int, None] = None):
        money = await self.start_game(ctx.author.id)

        try:
            if not n:
                await ctx.send(
                    embed=get_embed(
                        '금액 입력',
                        '걸 금액을 입력해주세요. `0`, `x`, `X`를 입력하면 취소됩니다.',
                    )
                )

                def message_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=message_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(embed=get_embed('시간 초과', '', 0xFF0000))
                    return

                n = msg.content.strip()

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

            deck = make_deck()
            hand = random.sample(deck, 5)

            view = PokerView(
                cog=self,
                ctx=ctx,
                bet=n,
                hand=hand,
                deck=deck,
            )

            msg = await ctx.send(embed=view.select_embed(), view=view)
            timed_out = await view.wait()

            if timed_out and not view.finished:
                view.disable_all_buttons()
                await msg.edit(
                    embed=get_embed('시간 초과', '포커 게임이 취소되었습니다.', 0xFF0000),
                    view=view,
                )

        finally:
            self.end_game(ctx.author.id)


async def setup(client):
    await client.add_cog(poker(client))
