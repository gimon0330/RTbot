import asyncio
import random
import typing

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


def make_deck():
    deck = [(rank, suit) for suit in SUITS for rank in range(2, 15)]
    random.shuffle(deck)
    return deck


def draw_card(deck):
    return deck.pop()


def format_card(card):
    rank, suit = card
    return f'{suit}{RANK_LABELS[rank]}'


def format_hand(hand):
    return '  '.join(format_card(card) for card in hand)


def card_value(card):
    rank, _ = card
    if rank == 14:
        return 11
    return min(rank, 10)


def hand_value(hand):
    total = sum(card_value(card) for card in hand)
    aces = sum(1 for rank, _ in hand if rank == 14)

    while total > 21 and aces > 0:
        total -= 10
        aces -= 1

    # 아직 11로 계산되고 있는 A가 하나 이상이면 소프트 핸드다.
    soft = aces > 0
    return total, soft


def is_blackjack(hand):
    return len(hand) == 2 and hand_value(hand)[0] == 21


def dealer_visible_text(hand):
    visible = hand[0]
    return f'{format_card(visible)}  🂠'


def dealer_visible_value(hand):
    return card_value(hand[0])


class BlackjackStartView(discord.ui.View):
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


class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet, deck, player_hand, dealer_hand):
        super().__init__(timeout=30)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.finished = False
        self.action_lock = asyncio.Lock()

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

    def playing_embed(self):
        player_total, player_soft = hand_value(self.player_hand)
        soft_label = ' (소프트)' if player_soft else ''

        return get_embed(
            '🃏 블랙잭',
            f'베팅 금액: **{format_money(self.bet)}** (차감 완료)\n\n'
            f'**내 카드**\n{format_hand(self.player_hand)}\n'
            f'합계: **{player_total}{soft_label}**\n\n'
            f'**딜러 카드**\n{dealer_visible_text(self.dealer_hand)}\n'
            f'보이는 합계: **{dealer_visible_value(self.dealer_hand)}**\n\n'
            '카드를 더 받으려면 `히트`, 멈추려면 `스탠드`를 누르세요.\n'
            '30초 동안 선택하지 않으면 자동으로 스탠드합니다.',
        )

    def result_embed(self, title, description, color):
        player_total, _ = hand_value(self.player_hand)
        dealer_total, _ = hand_value(self.dealer_hand)

        return get_embed(
            title,
            f'**내 카드**\n{format_hand(self.player_hand)}\n'
            f'합계: **{player_total}**\n\n'
            f'**딜러 카드**\n{format_hand(self.dealer_hand)}\n'
            f'합계: **{dealer_total}**\n\n'
            f'{description}',
            color,
        )

    async def settle(self, outcome, *, reason=None):
        if outcome == 'blackjack':
            payout = self.bet * 5 // 2
            profit = payout - self.bet
            title = '🃏 블랙잭!'
            text = (
                f'자연 블랙잭으로 승리했습니다.\n'
                f'지급액: **{format_money(payout)}**\n'
                f'순이익: **+{format_money(profit)}**'
            )
            color = 0xFFD700
        elif outcome == 'win':
            payout = self.bet * 2
            profit = self.bet
            title = '✅ 승리!'
            text = (
                f'{reason or "딜러보다 높은 점수입니다."}\n'
                f'지급액: **{format_money(payout)}**\n'
                f'순이익: **+{format_money(profit)}**'
            )
            color = 0x00FF00
        elif outcome == 'push':
            payout = self.bet
            title = '🤝 무승부'
            text = (
                f'{reason or "플레이어와 딜러의 점수가 같습니다."}\n'
                f'베팅금 **{format_money(payout)}**을 돌려받았습니다.'
            )
            color = 0xCCFFFF
        else:
            payout = 0
            title = '❌ 패배'
            text = (
                f'{reason or "딜러가 승리했습니다."}\n'
                f'베팅금 **{format_money(self.bet)}**을 잃었습니다.'
            )
            color = 0xFF0000

        new_money = await self.cog.add_payout(self.ctx.author.id, payout)
        text += f'\n현재 지갑: **{format_money(new_money)}**'
        return self.result_embed(title, text, color)

    def play_dealer(self):
        while True:
            dealer_total, _ = hand_value(self.dealer_hand)
            # 소프트 17을 포함해 17 이상에서 스탠드한다.
            if dealer_total >= 17:
                return
            self.dealer_hand.append(draw_card(self.deck))

    async def resolve_after_stand(self):
        self.play_dealer()
        player_total, _ = hand_value(self.player_hand)
        dealer_total, _ = hand_value(self.dealer_hand)

        if dealer_total > 21:
            return await self.settle('win', reason=f'딜러가 {dealer_total}로 버스트했습니다.')
        if player_total > dealer_total:
            return await self.settle('win')
        if player_total == dealer_total:
            return await self.settle('push')
        return await self.settle('lose', reason='딜러의 점수가 더 높습니다.')

    @discord.ui.button(label='히트', emoji='➕', style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.action_lock:
            if self.finished:
                if not interaction.response.is_done():
                    await interaction.response.send_message('이미 종료된 게임입니다.', ephemeral=True)
                return

            self.player_hand.append(draw_card(self.deck))
            player_total, _ = hand_value(self.player_hand)

            if player_total > 21:
                self.finished = True
                self.disable_all_buttons()
                await interaction.response.defer()
                embed = await self.settle(
                    'lose',
                    reason=f'카드 합계가 {player_total}로 21을 초과했습니다.',
                )
                await interaction.edit_original_response(embed=embed, view=self)
                self.stop()
                return

            if player_total == 21:
                self.finished = True
                self.disable_all_buttons()
                await interaction.response.defer()
                embed = await self.resolve_after_stand()
                await interaction.edit_original_response(embed=embed, view=self)
                self.stop()
                return

            await interaction.response.edit_message(embed=self.playing_embed(), view=self)

    @discord.ui.button(label='스탠드', emoji='✋', style=discord.ButtonStyle.success)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.action_lock:
            if self.finished:
                if not interaction.response.is_done():
                    await interaction.response.send_message('이미 종료된 게임입니다.', ephemeral=True)
                return

            self.finished = True
            self.disable_all_buttons()
            await interaction.response.defer()
            embed = await self.resolve_after_stand()
            await interaction.edit_original_response(embed=embed, view=self)
            self.stop()

    async def resolve_timeout(self, message):
        async with self.action_lock:
            if self.finished:
                return

            self.finished = True
            self.disable_all_buttons()
            embed = await self.resolve_after_stand()
            embed.description = (
                '⏰ **시간이 초과되어 자동으로 스탠드했습니다.**\n\n'
                + (embed.description or '')
            )
            await message.edit(embed=embed, view=self)
            self.stop()


class blackjack(commands.Cog):
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

    async def natural_result_embed(self, ctx, bet, player_hand, dealer_hand):
        player_blackjack = is_blackjack(player_hand)
        dealer_blackjack = is_blackjack(dealer_hand)

        if player_blackjack and dealer_blackjack:
            outcome = 'push'
            payout = bet
            title = '🤝 블랙잭 무승부'
            text = f'양쪽 모두 블랙잭입니다.\n베팅금 {format_money(bet)}을 돌려받았습니다.'
            color = 0xCCFFFF
        elif player_blackjack:
            outcome = 'blackjack'
            payout = bet * 5 // 2
            profit = payout - bet
            title = '🃏 자연 블랙잭!'
            text = (
                f'블랙잭 배당으로 {format_money(payout)}을 지급합니다.\n'
                f'순이익: +{format_money(profit)}'
            )
            color = 0xFFD700
        else:
            outcome = 'lose'
            payout = 0
            title = '❌ 딜러 블랙잭'
            text = f'딜러가 자연 블랙잭입니다.\n베팅금 {format_money(bet)}을 잃었습니다.'
            color = 0xFF0000

        new_money = await self.add_payout(ctx.author.id, payout)
        player_total, _ = hand_value(player_hand)
        dealer_total, _ = hand_value(dealer_hand)

        embed = get_embed(
            title,
            f'**내 카드**\n{format_hand(player_hand)}\n'
            f'합계: **{player_total}**\n\n'
            f'**딜러 카드**\n{format_hand(dealer_hand)}\n'
            f'합계: **{dealer_total}**\n\n'
            f'{text}\n현재 지갑: **{format_money(new_money)}**',
            color,
        )
        return outcome, embed

    @commands.command(name='블랙잭', aliases=['blackjack', '블잭', '21'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def blackjack_game(self, ctx, n: typing.Union[str, int, None] = None):
        if not begin_interaction(self.client, ctx.author.id, '블랙잭 게임'):
            raise errors.ActiveInteraction('진행 중인 작업')

        game_started = False
        try:
            money = await self.start_game(ctx.author.id)
            game_started = True

            if not n:
                await ctx.send(
                    embed=get_embed(
                        '금액 입력',
                        '걸 금액을 입력해주세요. `0`, `x`, `X`, `취소`를 입력하면 시작 전에 취소됩니다.',
                    )
                )

                def message_check(message):
                    return message.author == ctx.author and message.channel == ctx.channel

                try:
                    msg = await self.client.wait_for('message', check=message_check, timeout=20)
                except asyncio.TimeoutError:
                    await ctx.send(
                        embed=get_embed(
                            '시간 초과',
                            '게임을 시작하지 않아 돈은 차감되지 않았습니다.',
                            0xFF0000,
                        )
                    )
                    return

                n = msg.content.strip()
                if n in ['0', 'X', 'x', '취소']:
                    await ctx.send(
                        embed=get_embed(
                            '취소되었습니다.',
                            '게임을 시작하지 않아 돈은 차감되지 않았습니다.',
                            0xFF0000,
                        )
                    )
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

            start_view = BlackjackStartView(ctx.author.id)
            start_message = await ctx.send(
                embed=get_embed(
                    '🃏 블랙잭 시작 확인',
                    f'베팅 금액: **{format_money(n)}**\n\n'
                    '• `게임 시작`을 누르면 베팅금이 즉시 차감됩니다.\n'
                    '• 카드를 받은 뒤에는 취소하거나 환급받을 수 없습니다.\n'
                    '• 내 선택 시간이 초과되면 자동으로 스탠드합니다.\n'
                    '• 딜러는 소프트 17을 포함해 17 이상에서 스탠드합니다.\n\n'
                    '**배당**\n'
                    '자연 블랙잭: 2.5배 지급\n'
                    '일반 승리: 2배 지급\n'
                    '무승부: 원금 반환\n'
                    '패배: 지급 없음',
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
                        '확인하는 동안 잔액이 변경되어 블랙잭을 시작할 수 없습니다.',
                        0xFF0000,
                    ),
                    view=start_view,
                )
                return

            await start_message.edit(
                embed=get_embed(
                    '게임 시작',
                    f'베팅금 {format_money(n)}을 차감했습니다.\n'
                    f'남은 지갑: {format_money(remaining_money)}',
                ),
                view=start_view,
            )

            deck = make_deck()
            player_hand = [draw_card(deck), draw_card(deck)]
            dealer_hand = [draw_card(deck), draw_card(deck)]

            if is_blackjack(player_hand) or is_blackjack(dealer_hand):
                _, embed = await self.natural_result_embed(
                    ctx,
                    n,
                    player_hand,
                    dealer_hand,
                )
                await ctx.send(embed=embed)
                return

            view = BlackjackView(
                cog=self,
                ctx=ctx,
                bet=n,
                deck=deck,
                player_hand=player_hand,
                dealer_hand=dealer_hand,
            )
            game_message = await ctx.send(embed=view.playing_embed(), view=view)
            timed_out = await view.wait()

            if timed_out and not view.finished:
                await view.resolve_timeout(game_message)
        finally:
            if game_started:
                self.end_game(ctx.author.id)
            end_interaction(self.client, ctx.author.id)


async def setup(client):
    await client.add_cog(blackjack(client))
