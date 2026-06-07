import importlib


STAR_ICON = '⭐'
BRIGHT_STAR_ICON = '🌟'
GALAXY_STAR_ICON = '🌌'
BRIGHT_STAR_SIZE = 5
GALAXY_STAR_SIZE = 25


def compressed_star_icons(stars: int) -> str:
    if stars <= 0:
        return ''

    galaxy_stars, remain = divmod(stars, GALAXY_STAR_SIZE)
    bright_stars, small_stars = divmod(remain, BRIGHT_STAR_SIZE)

    return (
        GALAXY_STAR_ICON * galaxy_stars
        + BRIGHT_STAR_ICON * bright_stars
        + STAR_ICON * small_stars
    )


async def setup(client):
    reinforce_module = importlib.import_module('exts.reinforce')
    reinforce_module.star_icons = compressed_star_icons
    print('[OK] Applied reinforce star icon patch')
