import discord, asyncio, typing, aiomysql
import traceback
from discord.ext import commands
from random import randint
from utils import errors, checks

def get_embed(title, description='', color=0xCCFFFF): 
    return discord.Embed(title=title,description=description,color=color)

class money(commands.Cog):
    def __init__(self, client):
        self.client = client
        
        self.tictactoe = {}

        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        self._dobak.add_check(self.checks.money0up)
        self.dobak_all.add_check(self.checks.money0up)

        for cmds in self.get_commands():
            cmds.add_check(self.checks.registered)
            cmds.add_check(self.checks.blacklist)

    @commands.group(name='도박', invoke_without_command=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def _dobak(self, ctx, n:int):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money=int(fetch["money"])

                rand = randint(0, 100)
                if money < n: raise errors.NoMoney
                if n < 1: raise errors.morethan1
                if rand <= 11:
                    await ctx.send(ctx.author.mention+ " -1배ㅋㅋㅋㅋㅋ")
                    n = n * -2
                    if money + n < 0:  
                        await cur.execute('UPDATE userdata set money="0" WHERE id = %s', ctx.author.id)
                    else: await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money+n), ctx.author.id))
                elif rand <= 31:
                    await ctx.send(ctx.author.mention+ ' 0배 ㅋ')
                    await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money-n),ctx.author.id))
                elif rand <= 81:
                    await ctx.send(ctx.author.mention+ ' 1배!')
                else:
                    await ctx.send(ctx.author.mention+ ' 2배!!')
                    await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money+n),ctx.author.id))

    @_dobak.command(name='전체', aliases=['올인','올'])
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def dobak_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money=int(fetch["money"])
                rand = randint(0, 100)
                if money <= 0:
                    await ctx.send(embed=get_embed('<a:no:698461934613168199> | 돈이 부족합니다!','',0xff0000))
                    return
                if rand <= 40:
                    await ctx.send(ctx.author.mention+ " 0배 ㅋ")
                    money = 0
                elif rand <= 45:
                    await ctx.send(ctx.author.mention+ " 0.2배 ㅋㅋㅋㅋ")
                    money = money // 5
                elif rand <= 50:
                    await ctx.send(ctx.author.mention+ " 0.25배 ㅋㅋㅋㅋ")
                    money = money // 4
                elif rand <= 55:
                    await ctx.send(ctx.author.mention+ " 0.5배 ㅋㅋㅋㅋ")
                    money = money // 2
                elif rand <= 90:
                    await ctx.send(ctx.author.mention+ " 2배!!")
                    money = money * 2
                elif rand <= 95:
                    await ctx.send(ctx.author.mention+ " 3배!!")
                    money = money * 3
                elif rand <= 98:
                    await ctx.send(ctx.author.mention+ " 4배!!!")
                    money = money * 4
                else:
                    await ctx.send(ctx.author.mention+ " 5배!!!")
                    money = money * 5
                await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money), ctx.author.id))

    @commands.command(name='돈내놔', aliases=['돈줘',"돈받기","ㄷㅂㄱ"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def _give_me_money(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money=int(fetch["money"])
                await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money+400), ctx.author.id))
        await ctx.send(ctx.author.mention + " 400원 지급 완료!")

    @commands.group(name='내돈', aliases=['지갑','돈',"니돈","ㄴㄷ","ㄷ"], invoke_without_command=True)
    async def _mymoney(self, ctx, user: typing.Optional[discord.Member] = None):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if user:
                    if await cur.execute('SELECT * FROM userdata WHERE id = %s', user.id) == 0:
                        raise errors.NotRegistered
                else: 
                    user = ctx.author
                await cur.execute('SELECT money FROM userdata WHERE id = %s', user.id)
                fetch = await cur.fetchone()
                await ctx.send(embed=get_embed(f'💸 | {user} 님의 지갑',f"{fetch['money']} 원"))

    @_mymoney.command(name="한글")
    async def _mymoney_kor(self, ctx, user: typing.Optional[discord.Member]=None):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                if user:
                    if await cur.execute('SELECT * FROM userdata WHERE id = %s', user.id) == 0:
                        raise errors.NotRegistered
                else: 
                    user = ctx.author
                await cur.execute('SELECT money FROM userdata WHERE id = %s', user.id)
                fetch = await cur.fetchone()
                money = int(fetch["money"])

        suffix=['','만', '억', '조', '경', '해', '자', '양', '구', '간', '정', '재', '극','항하사','아승기','나유타','불가사의','무량대수','','','','','','','','구골','','','','','','','','','','','','','','','','','','','','','','','','']
        a=10000 ** 50
        if money > a: 
            await ctx.send(embed=get_embed("<a:no:698461934613168199> | 수가 너무 커서 계산이 불가합니다","구골^2 이상",0xff0000))
            return
        str_result = ''
        for i in range(0,51):
            if money >= a:
                str_result += f"{int(money // a)}{suffix[-i]} "
                money = money % a
            a=a//10000

        await ctx.send(embed=get_embed(f'💸 | {user} 님의 지갑',f"{str_result.strip()} 원"))
    
    @commands.command(name='송금', aliases=['입금'])
    @commands.guild_only()
    async def _give_money(self, ctx, muser:discord.Member, n:int):
        if muser == ctx.author:
            await ctx.send(embed=get_embed("<a:no:698461934613168199> | 본인에게 송금은 불가합니다.","다른 사람을 멘션해주세요",0xff0000))
            return
        if n <= 0: raise errors.morethan1
        try: sendmoney = int(n ** (3/4))
        except OverflowError: 
            await ctx.send(embed=get_embed("<a:no:698461934613168199> | 돈이 너무 커서 송금이 불가합니다.","더 작은수를 입력해주세요.",0xff0000))
            return
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:

                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money=int(fetch["money"])

                if await cur.execute('SELECT * FROM userdata WHERE id = %s', muser.id) == 0:
                    raise errors.NotRegistered
                await cur.execute('SELECT money FROM userdata WHERE id = %s', muser.id)
                fetch = await cur.fetchone()
                smoney=int(fetch["money"])

                if money < n: raise errors.NoMoney
                msg = await ctx.send(embed=get_embed("📝 | **송금**",f"**{ctx.author}**님이 **{muser}**님에게 송금\n**전송되는 금액 (수수료 차감)** = {sendmoney}"))
                emjs=['<a:yes:698461934198063104>','<a:no:698461934613168199>']
                for em in emjs: await msg.add_reaction(em)
                def check(reaction, user): return user == ctx.author and msg.id == reaction.message.id and str(reaction.emoji) in emjs
                try: reaction, user = await self.client.wait_for('reaction_add', check=check, timeout=20)
                except asyncio.TimeoutError: await asyncio.gather(msg.delete(),ctx.send(embed=get_embed('⏰ | 시간이 초과되었습니다!',"", 0xFF0000)))
                else:
                    e = str(reaction.emoji)
                    if e == '<a:yes:698461934198063104>':
                        await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money-n), ctx.author.id))
                        await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(smoney+sendmoney), muser.id))
                        await ctx.send(embed=get_embed(f"{ctx.author.name}님이 {muser.name}님에게 송금하셨습니다",f"송금 금액 : {n}\n\n받은 금액 (수수료 차감) : {sendmoney}"))
                        return
                    elif e == '<a:no:698461934613168199>':
                        await asyncio.gather(msg.delete(),ctx.send(embed=get_embed('<a:no:698461934613168199> | 취소 되었습니다!',"", 0xFF0000)))
                        return
        

    @commands.group(name='돈순위', aliases=['순위','랭크','순'], invoke_without_command=True)
    async def _money_rank(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata')
                fetch = await cur.fetchall()
        lis = []
        for a in fetch:
            lis.append([a["id"],int(a["money"])+int(a["bank"])])
        lis = sorted(lis, key=lambda x:x[1],reverse=True)
        embed=get_embed("알티봇 돈순위 전체 TOP 10")
        for a in range(0,10):
            if a == 0: medal = "<:1thropy:716106586333904986>"
            elif a == 1: medal = "<:silverthropy:736215959823712306>"
            elif a == 2: medal = "<:bronzethropy:736215949614645269>"
            else: medal = ":medal:"
            try: username=self.client.get_user(int(lis[a][0])).name
            except: username=lis[a][0]
            embed.add_field(name=f"{medal} {a+1}위 {username}님",value=f"{lis[a][1]}원",inline=False)
        await ctx.send(embed=embed)
        
    @_money_rank.command(name='서버', aliases=['섭'])
    async def money_rank_server(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata')
                fetch = await cur.fetchall()
        lis = []
        for a in fetch:
            lis.append([a["id"],int(a["money"])+int(a["bank"])])
        lis = sorted(lis, key=lambda x:x[1],reverse=True)
        embed=get_embed("알티봇 돈순위 전체 TOP 10")
        for a in range(0,10):
            if a == 0: medal = "<:1thropy:716106586333904986>"
            elif a == 1: medal = "<:silverthropy:736215959823712306>"
            elif a == 2: medal = "<:bronzethropy:736215949614645269>"
            else: medal = ":medal:"
            try: username=ctx.guild.get_member(int(lis[a][0])).name
            except: pass
            else: embed.add_field(name=f"{medal} {a+1}위 {username}님",value=f"{lis[a][1]}원",inline=False)
        await ctx.send(embed=embed)

    @commands.group(name='저금', invoke_without_command=True)
    async def _money_save(self, ctx, n:int):
        if n <= 0: raise errors.morethan1
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money = int(fetch["money"])
                bank = int(fetch["bank"])
                if money < n: raise errors.NoMoney
                await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money-n), ctx.author.id))
                await cur.execute('UPDATE userdata set bank=%s WHERE id = %s', (str(bank+n), ctx.author.id))
        await ctx.send(embed=get_embed("<a:yes:698461934198063104> | 저금 완료!"))
                                               
    @_money_save.command(name='전체', aliases=['다','올인',"전부","최대"])
    async def _money_save_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money = int(fetch["money"])
                bank = int(fetch["bank"])
                await cur.execute('UPDATE userdata set bank=%s WHERE id = %s', (str(money+bank),ctx.author.id))
                await cur.execute('UPDATE userdata set money="0" WHERE id = %s', ctx.author.id)
        await ctx.send(embed=get_embed("<a:yes:698461934198063104> | 저금 완료!"))

    @commands.group(name='인출', invoke_without_command=True)
    async def _money_withdraw(self, ctx, n:int):
        if n <= 0: raise errors.morethan1
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money = int(fetch["money"])
                bank = int(fetch["bank"])
                if bank < n: raise errors.NoMoney
                await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money+n), ctx.author.id))
                await cur.execute('UPDATE userdata set bank=%s WHERE id = %s', (str(bank-n), ctx.author.id))
        await ctx.send(embed=get_embed("<a:yes:698461934198063104> | 인출 완료!"))

    @_money_withdraw.command(name='전체', aliases=['다','올인'])
    async def _money_withdraw_all(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT * FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
                money = int(fetch["money"])
                bank = int(fetch["bank"])
                await cur.execute('UPDATE userdata set money=%s WHERE id = %s', (str(money+bank),ctx.author.id))
                await cur.execute('UPDATE userdata set bank="0" WHERE id = %s', ctx.author.id)
        await ctx.send(embed=get_embed("<a:yes:698461934198063104> | 인출 완료!"))

    @commands.command(name='은행잔고', aliases=['잔고','은행'])
    async def bank_money(self, ctx):
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute('SELECT bank FROM userdata WHERE id = %s', ctx.author.id)
                fetch = await cur.fetchone()
        await ctx.send(embed=get_embed(f"💳 | {ctx.author} 님의 은행잔고",f"{fetch['bank']} 원"))

async def setup(client):
    await client.add_cog(money(client))
