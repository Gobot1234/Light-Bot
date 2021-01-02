from typing import TypedDict


class ConfigCache(TypedDict):
    guild_id: int
    blacklisted: bool
    prefixes: list[str]
    logging_channel: int
    logged_events: list[str]
