# RTBOT Railway PostgreSQL 운영 메모

## Required Railway Variables

```env
DISCORD_TOKEN=your_discord_bot_token
DATABASE_URL=${{Postgres.DATABASE_URL}}
COMMAND_PREFIX=알티야 
DB_POOL_MAXSIZE=20
OWNER_ID=467666650183761920
ERROR_LOG_CHANNEL_ID=728788620000886854
GUILD_LOG_CHANNEL_ID=735563383277092874
```

`DATABASE_URL`의 `Postgres`는 Railway PostgreSQL 서비스 이름과 정확히 같아야 합니다.

## First deploy checklist

1. Railway PostgreSQL을 연결합니다.
2. 위 환경변수를 설정합니다.
3. Deploy합니다.
4. DB가 비어 있거나 schema가 꼬였으면 `migrations/001_fix_postgres_schema.sql`을 Railway PostgreSQL Query에서 실행합니다.
5. Discord에서 `알티야 가입`, `알티야 핑`, `알티야 내돈`을 테스트합니다.

## Current DB tables

- `userdata`: user wallet, bank, admin flag, blacklist flag
- `reinforce`: reinforce item uuid, item name, owner id, level

## Important notes

- Temporary debug commands were removed.
- Existing legacy DBs may still need the migration file because `CREATE TABLE IF NOT EXISTS` does not reshape old tables.
- Money values are intended to be numeric. New schema uses `NUMERIC(40, 0)`.
