from typing import TypedDict


class ConfigCache(TypedDict):
    guild_id: int
    prefixes: list[str]
