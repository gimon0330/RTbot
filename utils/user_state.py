from contextlib import asynccontextmanager


STATE_ATTR = 'active_user_interactions'


def store(client):
    data = getattr(client, STATE_ATTR, None)
    if data is None:
        data = {}
        setattr(client, STATE_ATTR, data)
    return data


def has_active_interaction(client, user_id: int) -> bool:
    return int(user_id) in store(client)


def active_interaction_reason(client, user_id: int):
    return store(client).get(int(user_id))


def begin_interaction(client, user_id: int, reason: str = 'interaction') -> bool:
    data = store(client)
    user_id = int(user_id)
    if user_id in data:
        return False
    data[user_id] = reason
    return True


def end_interaction(client, user_id: int):
    store(client).pop(int(user_id), None)


@asynccontextmanager
async def user_interaction(client, user_id: int, reason: str = 'interaction'):
    if not begin_interaction(client, user_id, reason):
        yield False
        return
    try:
        yield True
    finally:
        end_interaction(client, user_id)
