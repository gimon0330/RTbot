import discord
from discord.ext import commands


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


class _help(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group(name='도움', aliases=['명령어', '도움말'], invoke_without_command=True)
    async def _help(self, ctx):
        embed = get_embed('📌 | RTBOT 명령어')
        embed.add_field(
            name='📝 정보',
            value='`핑`, `정보`, `유저`, `주사위`, `업타임`, `프로필`, `프사`, `초대장`, `투표`, `문의`',
            inline=False,
        )
        embed.add_field(
            name='💰 경제',
            value='`가입`, `탈퇴`, `내돈`, `내돈 한글`, `돈내놔`, `송금`, `저금`, `저금 전체`, `인출`, `인출 전체`, `은행잔고`, `돈순위`, `돈순위 서버`, `도박`, `도박 전체`, `출석`, `상점`, `구매`, `인벤토리`',
            inline=False,
        )
        embed.add_field(
            name='🎮 게임 / 강화',
            value='`숫자맞추기`, `슬롯`, `포커`, `블랙잭`, `강화`, `강화 목록`, `강화 삭제`, `강화 판매`, `강화 이름변경`, `강화 순위 서버`, `강화 순위 전체`',
            inline=False,
        )
        embed.add_field(
            name='❓ 자세히 보기',
            value='`알티야 도움 정보`, `알티야 도움 경제`, `알티야 도움 게임`, `알티야 도움 관리자`',
            inline=False,
        )
        await ctx.send(embed=embed)

    @_help.command(name='정보')
    async def _help_info(self, ctx):
        embed = get_embed('📝 | 정보 명령어')
        embed.description = '\n'.join([
            '`알티야 핑` : 봇 지연시간을 확인합니다.',
            '`알티야 정보` : 봇 정보를 확인합니다.',
            '`알티야 유저` : 가입자 수와 서버 수를 확인합니다.',
            '`알티야 주사위` : 주사위를 굴립니다.',
            '`알티야 업타임` : 봇이 켜져 있던 시간을 확인합니다.',
            '`알티야 프로필 [@유저]` : 유저 프로필을 봅니다.',
            '`알티야 프사 [@유저]` : 유저 프로필 사진을 봅니다.',
            '`알티야 투표 <내용>` : 찬반 투표를 만듭니다.',
            '`알티야 문의 <내용>` : 관리자에게 문의를 보냅니다.',
        ])
        await ctx.send(embed=embed)

    @_help.command(name='경제', aliases=['도박', '돈'])
    async def _help_money(self, ctx):
        embed = get_embed('💰 | 경제 명령어')
        embed.description = '\n'.join([
            '`알티야 가입` : 경제 시스템에 가입합니다.',
            '`알티야 탈퇴` : 모든 데이터를 삭제하고 탈퇴합니다.',
            '`알티야 출석` : 하루 한 번 출석 보상을 받습니다.',
            '`알티야 내돈 [@유저]` : 지갑 잔액을 확인합니다.',
            '`알티야 은행잔고` : 은행 잔액을 확인합니다.',
            '`알티야 돈내놔` : 30초마다 400원을 받습니다.',
            '`알티야 송금 @유저 금액` : 수수료 차감 후 송금합니다.',
            '`알티야 저금 금액` / `알티야 저금 전체` : 지갑에서 은행으로 옮깁니다.',
            '`알티야 인출 금액` / `알티야 인출 전체` : 은행에서 지갑으로 옮깁니다.',
            '`알티야 돈순위` / `알티야 돈순위 서버` : 자산 순위를 봅니다.',
            '`알티야 도박 금액` / `알티야 도박 전체` : 도박을 합니다.',
            '`알티야 상점`, `알티야 구매 <아이템명> [개수]`, `알티야 인벤토리` : 상점 아이템을 이용합니다.',
        ])
        await ctx.send(embed=embed)

    @_help.command(name='게임', aliases=['미니게임', '강화'])
    async def _help_game(self, ctx):
        embed = get_embed('🎮 | 게임 / 강화 명령어')
        embed.description = '\n'.join([
            '`알티야 숫자맞추기 [금액]` : 숫자 맞추기 게임을 합니다.',
            '`알티야 슬롯 [금액]` : 슬롯 게임을 합니다.',
            '`알티야 포커 [금액]` : 카드 5장을 받고 한 번 교체하는 드로우 포커를 합니다.',
            '`알티야 블랙잭 [금액]` : 히트/스탠드 방식으로 딜러와 블랙잭을 합니다.',
            '`알티야 강화 <이름>` : 아이템을 강화합니다.',
            '`알티야 강화 목록` : 내 강화 아이템 목록을 봅니다.',
            '`알티야 강화 삭제 <이름>` : 강화 아이템을 삭제합니다.',
            '`알티야 강화 판매 <이름>` : 60레벨 이상 아이템을 판매합니다.',
            '`알티야 강화 이름변경 <기존이름> <새이름>` : 이름변경권을 사용합니다.',
            '`알티야 강화 순위 서버` / `알티야 강화 순위 전체` : 강화 랭킹을 봅니다.',
            '`알티야 가위바위보` : 현재 비활성화되어 있습니다.',
        ])
        await ctx.send(embed=embed)

    @_help.command(name='관리자', aliases=['어드민'])
    async def _help_admin(self, ctx):
        embed = get_embed('🛠️ | 관리자 명령어')
        embed.description = '\n'.join([
            '`알티야 관리자도움` : 관리자 명령어 전체를 봅니다.',
            '`알티야 강제가입 <유저ID>` / `알티야 유저등록확인 <유저ID>`',
            '`알티야 어드민추가 <유저ID>` / `알티야 어드민제거 <유저ID>`',
            '`알티야 블랙추가 <유저ID>` / `알티야 블랙제거 <유저ID>`',
            '`알티야 돈설정 <유저ID> <금액>` / `돈지급` / `돈차감` / `은행설정`',
            '`알티야 강화설정 <유저ID> <이름> <레벨>` 또는 `<유저ID> <레벨> <이름>`',
            '`알티야 강화삭제 <유저ID> <이름>` / `강화목록확인 <유저ID>`',
            '`알티야 아이템지급 <유저ID> <아이템명> <개수>` / `아이템회수` / `인벤확인`',
            '`알티야 공지보내 <내용>`',
        ])
        await ctx.send(embed=embed)


async def setup(client):
    await client.add_cog(_help(client))
