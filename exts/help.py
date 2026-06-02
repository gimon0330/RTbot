import discord
from discord.ext import commands 

def get_embed(title, description='', color=0xCCFFFF):
    embed=discord.Embed(title=title,description=description,color=color)
    return embed

class _help(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.group(name='도움', aliases=['명령어', '도움말'], invoke_without_command=True)
    async def _help(self, ctx):
        embed=get_embed("\📌 | **RTBOT 명령어**")
        embed.add_field(name='📝 | **정보**',value='`알티야 정보`,`알티야 프사`,`알티야 유저`,`알티야 프로필`,`알티야 핑`,`알티야 공지채널`',inline=False)
        embed.add_field(name='💰 | **도박**',value='`알티야 도박`,`알티야 저금`,`알티야 인출`,`알티야 내돈`,`알티야 은행잔고`,`알티야 돈내놔`,`알티야 돈줘`',inline=False)
        embed.add_field(name='💻 | **미니게임**',value='`알티야 강화 (물품/목록/삭제/판매)`,`알티야 가위바위보`,`알티야 슬롯`',inline=False)
        embed.add_field(name='❓ | **도움말**',value='`알티야 도움 (정보,도박,미니게임)`',inline=False)
        await ctx.send(embed=embed)
    
    @_help.command(name='정보')
    async def _help_1(self, ctx):
        embed=get_embed("\📝 | **정보 명령어**","""**알티야 정보** : 알티봇의 정보를 보여줍니다
**알티야 프사** : 멘션한 사람의 프사를 가져옵니다 (비우면 본인)
**알티야 유저** : 알티봇의 게임중인 유저수를 보여줍니다.
**알티야 프로필** : 멘션한 사람의 프로필을 가져옵니다 (비우면 본인)
**알티야 핑** : 알티봇의 핑을 보여줍니다.
**알티야 공지채널** : 알티봇의 전체 공지채널을 설정합니다.""")
        await ctx.send(embed=embed)

    @_help.command(name='도박')
    async def _help_2(self, ctx):
        embed=get_embed("\📝 | **도박 명령어**","""**알티야 도박 (액수 / 올인)** : 도박을 시작합니다.
**알티야 저금 (액수 / 올인)** : 현재 모은 돈을 은행에 저금합니다.
**알티야 인출 (액수 / 올인)** : 저금된 돈을 꺼내옵니다.
**알티야 내돈** : 현재 잔액을 표시합니다.
**알티야 은행잔고** : 저금한 금액을 확인합니다.
**알티야 돈내놔** : 알티봇이 돈을 줍니다.
**알티야 돈줘 (@멘션) (액수)** : 멘션 한 사람에게 일정량의 돈을 줍니다.""")
        await ctx.send(embed=embed)

    @_help.command(name='미니게임')
    async def _help_4(self, ctx):
        embed=get_embed("\📝 | **미니게임 명령어**","""**알티야 숫자맞추기** : 숫자맞추기 게임을 합니다. 
**알티야 가위바위보 (빠,묵,찌)** : 가위바위보를 합니다 이긴사람이 1000원을 갖습니다.
**알티야 슬롯 (액수)** 슬롯게임을 합니다.
**알티야 낚시** : 낚시를 합니다. (개발중인 명령어)""")
        await ctx.send(embed=embed)

async def setup(client):
    await client.add_cog(_help(client))