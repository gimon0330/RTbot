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
    """Load config from JSON and allow Railway environment variables to override secrets."""
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    else:
        config = {}

    config.setdefault("db", {})

    config["token"] = os.getenv("DISCORD_TOKEN", config.get("token"))
    config["command_prefix"] = os.getenv(
        "COMMAND_PREFIX",
        config.get("command_prefix", "알티야 "),
    )

    db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or config["db"].get("url")
    )

    if db_url:
        config["db"] = {
            "url": db_url,
            "maxsize": int(os.getenv("DB_POOL_MAXSIZE", config["db"].get("maxsize", 20))),
        }
    else:
        config["db"]["host"] = os.getenv("PGHOST", os.getenv("DB_HOST", config["db"].get("host", "localhost")))
        config["db"]["port"] = int(os.getenv("PGPORT", os.getenv("DB_PORT", config["db"].get("port", 5432))))
        config["db"]["user"] = os.getenv("PGUSER", os.getenv("DB_USER", config["db"].get("user")))
        config["db"]["password"] = os.getenv("PGPASSWORD", os.getenv("DB_PASSWORD", config["db"].get("password")))
        config["db"]["database"] = os.getenv(
            "PGDATABASE",
            os.getenv("DB_NAME", config["db"].get("database", config["db"].get("db"))),
        )
        config["db"]["maxsize"] = int(os.getenv("DB_POOL_MAXSIZE", config["db"].get("maxsize", 20)))

    missing = []

    if not config.get("token"):
        missing.append("DISCORD_TOKEN or config.token")

    if not config["db"].get("url"):
        for key in ("user", "password", "database"):
            if not config["db"].get(key):
                missing.append(f"PostgreSQL {key}")

    if missing:
        raise RuntimeError("Missing required configuration: " + ", ".join(missing))

    return config


config = load_config()


async def connect_db():
    return await aiomysql.create_pool(**config["db"])


def build_intents():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    return intents


async def main():
    pool = await connect_db()

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
            await client.load_extension(ext_name)
        except Exception as exc:
            print(f"[WARN] Failed to load extension {ext_name}: {exc.__class__.__name__}: {exc}")
        else:
            print(f"[OK] Loaded extension {ext_name}")

    await client.start(config["token"])


asyncio.run(main())
