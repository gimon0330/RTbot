import asyncio
import json
import os
from pathlib import Path

import aiomysql
import discord
from discord.ext import commands


CONFIG_PATH = Path(os.getenv("RTBOT_CONFIG", "./config/config.json"))
DEFAULT_EXTENSIONS_DIR = Path("./exts")


def load_config() -> dict:
    """Load config from JSON and allow environment variables to override secrets.

    The original project was configured only through config/config.json. Keeping that
    behavior preserves compatibility, while env overrides make the public repository
    safer to clone and run without committing real tokens or DB passwords.
    """
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    else:
        config = {}

    config.setdefault("db", {})
    config["token"] = os.getenv("DISCORD_TOKEN", config.get("token"))
    config["command_prefix"] = os.getenv("COMMAND_PREFIX", config.get("command_prefix", "알티야 "))
    config["db"]["host"] = os.getenv("DB_HOST", config["db"].get("host", "localhost"))
    config["db"]["user"] = os.getenv("DB_USER", config["db"].get("user"))
    config["db"]["password"] = os.getenv("DB_PASSWORD", config["db"].get("password"))
    config["db"]["db"] = os.getenv("DB_NAME", config["db"].get("db"))
    config["db"]["charset"] = os.getenv("DB_CHARSET", config["db"].get("charset", "utf8mb4"))
    config["db"]["maxsize"] = int(os.getenv("DB_POOL_MAXSIZE", config["db"].get("maxsize", 20)))

    missing = []
    if not config.get("token"):
        missing.append("DISCORD_TOKEN or config.token")
    for key in ("user", "password", "db"):
        if not config["db"].get(key):
            missing.append(f"DB_{key.upper()} or config.db.{key}")
    if missing:
        raise RuntimeError("Missing required configuration: " + ", ".join(missing))

    return config


config = load_config()
loop = asyncio.get_event_loop()


async def connect_db():
    return await aiomysql.create_pool(
        host=config["db"]["host"],
        user=config["db"]["user"],
        password=config["db"]["password"],
        db=config["db"]["db"],
        charset=config["db"]["charset"],
        autocommit=True,
        maxsize=config["db"]["maxsize"],
    )


def build_intents():
    intents = discord.Intents.default()
    if hasattr(intents, "message_content"):
        intents.message_content = True
    return intents


pool = loop.run_until_complete(connect_db())

client = commands.AutoShardedBot(
    command_prefix=config["command_prefix"],
    intents=build_intents(),
)
client.pool = pool


for ext_path in sorted(DEFAULT_EXTENSIONS_DIR.glob("*.py")):
    if ext_path.name.startswith("_"):
        continue
    ext_name = f"exts.{ext_path.stem}"
    try:
        client.load_extension(ext_name)
    except Exception as exc:
        print(f"[WARN] Failed to load extension {ext_name}: {exc.__class__.__name__}: {exc}")
    else:
        print(f"[OK] Loaded extension {ext_name}")


client.run(config["token"])
