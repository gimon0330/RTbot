# RTBOT

RTBOT은 2020년부터 2021년까지 개발한 **Discord text-based minigame bot**입니다.

당시 1,500개 이상의 Discord server와 4,000명 이상의 user가 사용했던 프로젝트이며, 현재는 개발이 중단되어 코드가 공개된 archival repository입니다.

> 이 프로젝트는 오래된 `discord.py` 기반 코드입니다. 현재 Discord API와 최신 `discord.py` 버전에서는 추가 수정 없이 바로 동작하지 않을 수 있습니다.

## Overview

RTBOT은 Discord server 안에서 텍스트 명령어를 통해 미니게임, 재화 시스템, 강화 시스템, 유저 등록, 관리자 기능 등을 사용할 수 있도록 만든 봇입니다.

처음 Python과 Discord bot 개발을 배워가며 만든 프로젝트라 코드 스타일은 현재 기준으로 다듬어지지 않은 부분이 많습니다. 하지만 실제 사용자가 많았고, 피드백을 받으며 기능을 고쳐나갔다는 점에서 개인적으로 큰 의미가 있는 프로젝트입니다.

## Features

- Discord text command 기반 bot
- Auto sharding 기반 실행 구조
- Extension/Cog 기반 기능 분리
- User registration
- Economy system
- Minigames
- Reinforcement system
- Admin commands
- Guild join/remove logging
- Global error handling

## Repository Structure

```text
.
├── rtbot2.py
├── requirements.txt
├── config/
│   └── config.example.json
├── exts/
│   ├── admin.py
│   ├── basecmds.py
│   ├── chat.py
│   ├── event.py
│   ├── help.py
│   ├── minigame.py
│   ├── money.py
│   ├── reg.py
│   ├── reinforce.py
│   └── supportserver.py
└── utils/
    ├── basemgr.py
    ├── checks.py
    ├── errors.py
    └── permutil.py
```

## Main Entry

The main entrypoint is:

```text
rtbot2.py
```

`rtbot2.py` performs the following work:

1. Loads configuration
2. Connects to MySQL using `aiomysql`
3. Creates an `AutoShardedBot`
4. Loads every Python extension in `exts/`
5. Starts the Discord bot

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare configuration

Copy the example config file:

```bash
cp config/config.example.json config/config.json
```

Then edit `config/config.json`:

```json
{
  "token": "YOUR_DISCORD_BOT_TOKEN",
  "command_prefix": "알티야 ",
  "db": {
    "host": "localhost",
    "user": "rtbot_user",
    "password": "rtbot_password",
    "db": "rtbot",
    "charset": "utf8mb4",
    "maxsize": 20
  }
}
```

You can also override secret values using environment variables:

```bash
export DISCORD_TOKEN="YOUR_DISCORD_BOT_TOKEN"
export COMMAND_PREFIX="알티야 "
export DB_HOST="localhost"
export DB_USER="rtbot_user"
export DB_PASSWORD="rtbot_password"
export DB_NAME="rtbot"
export DB_CHARSET="utf8mb4"
export DB_POOL_MAXSIZE="20"
```

### 3. Run

```bash
python rtbot2.py
```

## Configuration Safety

Real bot tokens and DB credentials should not be committed to the repository.

This repository now ignores:

```text
config/config.json
.env
*.env
__pycache__/
*.pyc
```

Use `config/config.example.json` as the template for local configuration.

## Code Review Notes

The original code was written as an early Python/Discord bot project. While reviewing the repository, the following points stood out.

### 1. Configuration and secrets

Previously, the bot assumed that `config/config.json` always existed and contained every secret value. This made local setup fragile and increased the risk of accidentally committing secrets.

Updated:

- Added `config/config.example.json`
- Added environment variable override support
- Added `.gitignore` entries for real config and `.env` files

### 2. Startup structure

The bot uses `rtbot2.py` as the main runtime and loads every `.py` file under `exts/` as a Discord extension.

Updated:

- Extension loading is now sorted for deterministic startup
- Extension load failures are logged instead of crashing the whole startup immediately
- DB pool max size is configurable instead of hardcoded
- Discord message content intent is enabled when supported by the installed library

### 3. Generated files

The repository included generated `__pycache__/*.pyc` files. These are not source code and should not be versioned.

Updated:

- Removed generated pycache files
- Added `.gitignore` rules to prevent them from being committed again

### 4. Error handling

The old `event.py` handled many errors, but there were a few rough edges:

- Channel IDs were hardcoded repeatedly
- Missing logging channels could cause secondary errors
- A stale `self.ctx` reference existed in one branch
- Some duplicated error branches existed
- Raw tracebacks contained leftover debug text

Updated:

- Introduced named channel ID constants
- Added `safe_send_channel()` helper
- Added `cog_unload()` to cancel the background presence task
- Removed the stale `self.ctx` branch
- Cleaned the unknown error reporting message

## Known Limitations

This repository is preserved mostly as an archival project. Some parts still need deeper refactoring if the bot is revived.

Recommended future work:

- Migrate to a modern maintained Discord library version
- Replace scattered SQL queries with a repository/service layer
- Add DB migration files for required tables
- Convert hardcoded channel IDs and owner IDs into config values
- Add tests for economy and minigame logic
- Split large Cogs into smaller feature modules
- Replace bare `except:` blocks with specific exception handling
- Add structured logging instead of `print()` and raw traceback messages

## Personal Note

RTBOT is one of the projects that made development feel real to me.

It was not just code that ran on my computer. Many people actually invited the bot, used it in their servers, reported bugs, and gave feedback. That experience gave me a strong sense of achievement, and it taught me that development is not only about writing clever code, but also about caring about users, listening to feedback, and continuing to improve something people use.

That mindset is still one of the reasons I continue to build software.

## Status

Development is currently stopped.

The code is public for archival and portfolio purposes.
