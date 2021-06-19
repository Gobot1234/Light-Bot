from __future__ import annotations

import asyncio
import logging
import traceback
from pathlib import Path
from typing import Any

import aiohttp
import asyncpg
import discord
import steam
from discord.ext import commands
from steam.ext.commands.bot import resolve_path

from light import config
from light.db import Config

from .cogs.utils import logger
from .cogs.utils.context import Context
from .cogs.utils.formats import human_join
from .cogs.utils.help import EmbedHelpCommand

bot: Light


class Light(commands.Bot):
    def __init__(self, db: asyncpg.Pool) -> None:
        mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)
        intents = discord.Intents.default()
        super().__init__(
            command_prefix=Light.command_prefix,
            case_insensitive=True,
            intents=intents,
            allowed_mentions=mentions,
            help_command=EmbedHelpCommand(),
        )

        self.first_ready = True
        self.db = db
        self.session = aiohttp.ClientSession()
        self.client = steam.Client()
        self.launch_time = discord.utils.utcnow()
        self.configs: dict[int, Config] = {}

        self.setup_logging()

    async def command_prefix(self, message: discord.Message) -> list[str]:
        try:
            prefixes = ["=", ""] if message.guild is None else self.configs[message.guild.id].prefixes
        except KeyError:
            prefixes = ["="]
            self.configs[message.guild.id] = await Config.insert(
                guild_id=message.guild.id, blacklisted=False, prefixes=prefixes
            )
        return commands.when_mentioned_or(*prefixes)(self, message)

    def setup_logging(self) -> None:
        self.webhook = discord.Webhook.from_url(config.WEBHOOK_URL, session=self.session)

        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("steam").setLevel(logging.INFO)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        self.log = logger.WebhookLogger(self.webhook)
        asyncio.create_task(self.log.sender())
        self.log.info("Finished setting up logging")

    async def start(self) -> None:
        for extension in (
            extensions := [
                f
                for f in Path("bot/cogs").iterdir()
                if f.is_file() and f.suffix == ".py" and not f.name.startswith("_")
            ]
        ):
            self.load_extension(resolve_path(extension))

        self.load_extension("jishaku")

        for guild in await Config.fetch():
            if guild.blacklisted and (actual_guild := self.get_guild(guild.guild_id)):
                await actual_guild.leave()
                continue
            self.configs[guild.guild_id] = guild

        print(f"Extensions to be loaded are {human_join([str(f) for f in extensions])}")
        await asyncio.gather(
            self.client.start(config.STEAM_USERNAME, config.STEAM_PASSWORD, shared_secret=config.STEAM_SHARED_SECRET),
            super().start(config.TOKEN),
        )

    async def on_ready(self) -> None:
        if not self.first_ready:
            return

        self.first_ready = False
        await self.client.wait_until_ready()
        print(f"Logged in as: {self.user} - {self.user.id} | {self.client.user} - {self.client.user.id64}")
        self.log.info(f"Logged in as: {self.user} - {self.user.id} | {self.client.user} - {self.client.user.id64}")

    async def on_error(self, event: str, *args: Any, **kwargs: Any) -> None:
        self.log.error(f"Error in {event}", exc_info=True)
        traceback.print_exc()

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
    def client_secret(self) -> str:
        return config.CLIENT_SECRET


async def setup(db: asyncpg.Pool) -> Light:
    global bot
    bot = Light(db)
    return bot
