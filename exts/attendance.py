from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import aiomysql
import discord
from discord.ext import commands

from utils import checks

KST = ZoneInfo('Asia/Seoul')
BASE_REWARD = 10000
STREAK_BONUS = 2000
MAX_STREAK_BONUS = 30000
WEEKLY_BONUS = 50000


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


def today_kst():
    return datetime.now(KST).date()


def reward_for_streak(streak: int):
    daily_bonus = min(streak * STREAK_BONUS, MAX_STREAK_BONUS)
    reward = BASE_REWARD + daily_bonus
    weekly_bonus = WEEKLY_BONUS if streak % 7 == 0 else 0
    return reward + weekly_bonus, daily_bonus, weekly_bonus


class Attendance(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.pool = self.client.pool
        self.checks = checks.checks(self.pool)

        for command in self.get_commands():
            command.add_check(self.checks.registered)
            command.add_check(self.checks.blacklist)

    async def ensure_table(self, cur):
        await cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS attendance (
                user_id BIGINT PRIMARY KEY,
                last_checkin_date TEXT,
                streak INTEGER NOT NULL DEFAULT 0,
                total_checkins INTEGER NOT NULL DEFAULT 0
            )
            '''
        )

    @commands.command(name='출석', aliases=['출석체크', 'ㅊㅅ'])
    async def attendance(self, ctx):
        today = today_kst()
        yesterday = today - timedelta(days=1)

        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await self.ensure_table(cur)

                await cur.execute('SELECT * FROM attendance WHERE user_id = %s', ctx.author.id)
                row = await cur.fetchone()

                if row is not None and row.get('last_checkin_date') == today.isoformat():
                    await ctx.send(embed=get_embed(
                        '📅 이미 출석했습니다',
                        f'오늘은 이미 출석체크를 완료했습니다.\n현재 연속 출석: {int(row["streak"]):,}일',
                        0xFF0000,
                    ))
                    return

                if row is None:
                    streak = 1
                    total_checkins = 1
                    await cur.execute(
                        'INSERT INTO attendance (user_id, last_checkin_date, streak, total_checkins) VALUES (%s, %s, %s, %s)',
                        (ctx.author.id, today.isoformat(), streak, total_checkins),
                    )
                else:
                    previous_date = row.get('last_checkin_date')
                    if previous_date == yesterday.isoformat():
                        streak = int(row['streak']) + 1
                    else:
                        streak = 1
                    total_checkins = int(row['total_checkins']) + 1
                    await cur.execute(
                        'UPDATE attendance SET last_checkin_date = %s, streak = %s, total_checkins = %s WHERE user_id = %s',
                        (today.isoformat(), streak, total_checkins, ctx.author.id),
                    )

                reward, daily_bonus, weekly_bonus = reward_for_streak(streak)

                await cur.execute('SELECT money FROM userdata WHERE id = %s', ctx.author.id)
                user_row = await cur.fetchone()
                money = int(user_row['money'])
                await cur.execute('UPDATE userdata SET money = %s WHERE id = %s', (str(money + reward), ctx.author.id))

        lines = [
            f'{ctx.author.mention} 출석 완료!',
            f'보상: {reward:,}원',
            f'연속 출석: {streak:,}일',
            f'누적 출석: {total_checkins:,}일',
        ]
        if daily_bonus:
            lines.append(f'연속 보너스: {daily_bonus:,}원')
        if weekly_bonus:
            lines.append(f'7일 보너스: {weekly_bonus:,}원')

        await ctx.send(embed=get_embed('📅 출석체크 완료', '\n'.join(lines)))


async def setup(client):
    await client.add_cog(Attendance(client))
