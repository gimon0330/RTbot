SHOP_ITEMS = {
    'normal_protect': {
        'name': '일반강화보호권',
        'aliases': ['일반보호권', '일반보호', '강화보호권'],
        'price': 300_000,
        'description': '100레벨 미만 일반 강화 실패 시 레벨 하락을 1회 방지합니다.',
    },
    'normal_booster': {
        'name': '일반강화부스터',
        'aliases': ['일반부스터', '강화부스터'],
        'price': 150_000,
        'description': '100레벨 미만 일반 강화 1회 성공률을 5% 올립니다.',
    },
    'normal_super_booster': {
        'name': '고급강화부스터',
        'aliases': ['고급부스터'],
        'price': 450_000,
        'description': '100레벨 미만 일반 강화 1회 성공률을 10% 올립니다.',
    },
    'star_drop_protect': {
        'name': '스타하락방지권',
        'aliases': ['하락방지권', '스타하락방지'],
        'price': 1_500_000,
        'description': '스타강화 실패 시 별 하락을 1회 방지합니다. 파괴는 막지 못합니다.',
    },
    'star_booster': {
        'name': '스타부스터',
        'aliases': ['스타강화부스터'],
        'price': 2_000_000,
        'description': '스타강화 1회 성공률을 5% 올립니다.',
    },
    'star_destroy_protect': {
        'name': '스타파괴방지권',
        'aliases': ['파괴방지권', '스타파괴방지'],
        'price': 8_000_000,
        'description': '스타강화 파괴 발생 시 파괴 대신 1성 하락으로 처리합니다.',
    },
    'perfect_protect': {
        'name': '완전보호권',
        'aliases': ['완전보호'],
        'price': 20_000_000,
        'description': '강화 실패/파괴의 불이익을 1회 방지합니다.',
    },
    'rename_ticket': {
        'name': '이름변경권',
        'aliases': ['이름변경', '닉변권'],
        'price': 500_000,
        'description': '본인 강화 아이템의 이름을 1회 변경합니다.',
    },
    'premium_appraisal': {
        'name': '프리미엄감정권',
        'aliases': ['감정권', '프감'],
        'price': 300_000,
        'description': '강화 아이템 판매 시 판매가를 5% 올립니다.',
    },
}


ITEM_ALIASES = {}
for key, item in SHOP_ITEMS.items():
    ITEM_ALIASES[item['name']] = key
    ITEM_ALIASES[key] = key
    for alias in item.get('aliases', []):
        ITEM_ALIASES[alias] = key


def resolve_item_key(name: str):
    if name is None:
        return None
    return ITEM_ALIASES.get(name.replace(' ', '').strip())


def get_item(key: str):
    return SHOP_ITEMS.get(key)


def format_money(value: int) -> str:
    return f'{int(value):,}원'
