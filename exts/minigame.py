import asyncio
import random
import typing
from random import randint

import aiomysql
import discord
from discord.ext import commands

from utils import errors, checks
from utils.views import ask_confirm


def get_embed(title, description='', color=0xCCFFFF):
    return discord.Embed(title=title, description=description, color=color)


class minigame(commands.Cog):
    def