from datetime import datetime
from uuid import UUID

import asyncpg
from donphan import Column, create_pool

from .. import config, utils
from .table import DotRecord, SQLType, Table


class Config(Table):
    guild_id: SQLType.BigInt = Column(primary_key=True)
    blacklisted: bool = False
    prefixes: list[str]


class SteamService(Table):
    created_at: datetime = Column(primary_key=True)  #: When the service was checked
    percent_up: float  #: The percentage of CMs that are responding to pings
    online_count: int  #: The number of players online according to https://store.steampowered.com/stats/userdata.json
    community_status: bool  #: Whether or not steamcommunity.com was up
    store_status: bool  #: Whether or not store.steampowered.com was up
    api_status: bool  #: Whether or not the api.steampowered.com was up


class SteamUser(Table):
    id: SQLType.BigInt = Column(primary_key=True)  # Snowflake
    id64: SQLType.BigInt  # SteamID.id64
    access_token: str  # from db.types.AccessTokenResponse
    refresh_token: str
    expires: datetime
    session_id: UUID = Column(primary_key=True)


async def setup() -> asyncpg.Pool:
    dsn = f"postgres://{config.DATABASE_USER}:{config.DATABASE_PASSWORD}@localhost/{{name}}"
    try:
        db = await create_pool(
            dsn=dsn.format(name=config.DATABASE_NAME),
            command_timeout=10,
            record_class=DotRecord,
            set_as_default=True,
        )
    except asyncpg.InvalidCatalogNameError:
        async with utils.aclosing(await asyncpg.connect(dsn.format(name="template1"))) as temp:
            await temp.execute(f"""CREATE DATABASE {config.DATABASE_NAME} OWNER {config.DATABASE_USER}""")

        return await setup()

    await Table.create_all()
    return db
