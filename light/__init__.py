# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import discord
import steam
from asyncpg.pool import Pool
from discord.ext import commands
from donphan import create_pool
from steam.ext.commands.bot import resolve_path

from . import config
from .cogs.utils import logger
from .cogs.utils.context import Context
from .cogs.utils.db import Config, DotRecord, Table
from .cogs.utils.formats import format_error, human_join


def get_prefix(bot: Light, message: discord.Message) -> list[str]:
    prefixes = ["=", ""] if message.guild is None else bot.config_cache[message.guild.id].prefixes
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Light(commands.Bot):
    def __init__(self):
        mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)
        intents = discord.Intents.default()
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            intents=intents,
            allowed_mentions=mentions,
            owner_id=340869611903909888,
        )
        self.first_ready = True
        self.guilds_to_leave: list[int] = []

        self.log: Optional[logger.WebhookLogger] = None
        self.db: Optional[Pool] = None
        self.config_cache: dict[int, Config] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.client = steam.Client()
        self.launch_time = datetime.utcnow()
        self.initial_extensions = [
            f.with_suffix("")
            for f in Path("cogs").iterdir()
            if f.is_file() and f.suffix == ".py" and not f.name.startswith("_")
        ]

    async def setup_logging(self) -> None:
        self.webhook_adapter = adapter = discord.AsyncWebhookAdapter(self.session)
        self.webhook = discord.Webhook.from_url(config.WEBHOOK_URL, adapter=adapter)

        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("steam").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        self.log = logger.WebhookLogger(adapter)
        self.log.info("Finished setting up logging")

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

        await self.setup_logging()
        for extension in self.initial_extensions:
            self.load_extension(resolve_path(extension))

        self.load_extension("jishaku")

        try:
            self.db = await create_pool(dsn=config.DATABASE_URL, command_timeout=10, record_class=DotRecord)
        except Exception as exc:
            traceback.print_exc()
            self.log.error(f"Could not set up PostgreSQL. Exiting...", exc_info=exc)
            return await asyncio.sleep(600)
        else:
            async with self.db.acquire() as connection:
                await Table.create_tables(connection)

            for guild in await Config.fetchall():
                if guild.blacklisted:
                    self.guilds_to_leave.append(guild.guild_id)
                    continue
                self.config_cache[guild.guild_id] = guild

        print(f"Extensions to be loaded are {human_join([str(f) for f in self.initial_extensions])}")

        self.log.info("Booting up")
        await asyncio.gather(
            self.client.start(config.STEAM_USERNAME, config.STEAM_PASSWORD, shared_secret=config.STEAM_SHARED_SECRET),
            super().start(config.TOKEN),
        )

    async def on_ready(self) -> None:
        if not self.first_ready:
            return

        for guild_id in self.guilds_to_leave:
            if guild := discord.utils.get(self.guilds, id=guild_id):
                await guild.leave()

        await self.client.wait_until_ready()
        print(f"Logged as: ({self.user} - {self.user.id}) ({self.client.user} - {self.client.user.id64})")
        self.log.info(f"Logged as: ({self.user} - {self.user.id}) ({self.client.user} - {self.client.user.id64})")
        self.first_ready = False

    async def close(self) -> None:
        try:
            self.log.info("About to close the bot")
            if self.db is not None:
                await self.db.close()
            if self.session is not None:
                await self.session.close()
            if self.client is not None:
                await self.client.close()
        finally:
            await super().close()

    async def get_context(self, message: discord.Message) -> Context:
        return await super().get_context(message, cls=Context)

    @property
    def owner(self) -> discord.User:
        return self.get_user(self.owner_id)
