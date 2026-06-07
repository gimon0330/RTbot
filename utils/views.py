import discord

from utils.user_state import user_interaction


class ConfirmView(discord.ui.View):
    def __init__(self, author_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author_id:
            return True
        await interaction.response.send_message("이 버튼은 명령어를 실행한 사람만 사용할 수 있어요.", ephemeral=True)
        return False

    async def on_timeout(self):
        self.value = None
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="확인", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="취소", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


async def ask_confirm(ctx, *, embed=None, content=None, timeout: float = 30.0, reason: str = '버튼 응답 대기'):
    async with user_interaction(ctx.bot, ctx.author.id, reason) as acquired:
        if not acquired:
            await ctx.send('이미 다른 작업을 진행 중입니다. 먼저 진행 중인 버튼/입력을 완료해주세요.')
            return None, None

        view = ConfirmView(ctx.author.id, timeout=timeout)
        message = await ctx.send(content=content, embed=embed, view=view)
        await view.wait()

        if view.value is None:
            try:
                await message.edit(view=view)
            except discord.HTTPException:
                pass

        return view.value, message
