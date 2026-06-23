async def setup(client):
    minigame = client.get_cog('minigame')
    command = client.get_command('숫자맞추기')

    if minigame is None or command is None:
        raise RuntimeError('숫자맞추기 명령어 또는 minigame Cog를 찾을 수 없습니다.')

    command.add_check(minigame.checks.registered)
    command.add_check(minigame.checks.blacklist)
