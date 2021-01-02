# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from asyncpg.pool import create_pool, Pool
from discord.ext import commands

from . import config
from .cogs.utils.context import Context
from .cogs.utils.db import Table, Config
from .cogs.utils.formats import format_error
from .cogs.utils.typings import ConfigCache


__version__ = "0.0.2"


def get_prefix(bot: Light, message: discord.Message):
    if message.guild is None:
        prefixes = ["=", ""]
    else:
        prefixes = bot.config_cache[message.guild.id]["prefixes"]
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Light(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, case_insensitive=True)
        self.first_ready = True
        self.guilds_to_leave: list[int] = []

        self.log: Optional[logging.Logger] = None
        self.db: Optional[Pool] = None
        self.config_cache: dict[int, ConfigCache] = {}
        self.owner_ids = {340869611903909888, 468518451728613408}
        self.session: Optional[aiohttp.ClientSession] = None
        self.launch_time = datetime.utcnow()
        cogs = Path("cogs")
        self.initial_extensions = [f.with_suffix("") for f in cogs.iterdir() if f.is_file()]

    async def get_context(self, message: discord.Message) -> Context:
        return await super().get_context(message, cls=Context)

    def setup_logging(self):
        log_level = logging.DEBUG
        format_string = "%(asctime)s : %(name)s - %(levelname)s | %(message)s"
        log_format = logging.Formatter(format_string)

        log_file = Path("logs", "bot.log")
        log_file.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            filename=f'logs/out--{datetime.now().strftime("%d-%m-%Y")}.log', encoding="utf-8", mode="w"
        )
        file_handler.setFormatter(log_format)

        root_log = logging.getLogger()
        root_log.setLevel(log_level)
        root_log.addHandler(file_handler)

        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("steam").setLevel(logging.WARNING)
        self.log = logging.getLogger("Light")
        self.log.info("Finished setting up logging")

    async def start(self):
        self.setup_logging()
        self.log.info("Setting up DB")
        try:
            self.db = await create_pool(database="postgres", user="postgres", password="DataBase", command_timeout=60)
        except Exception as e:
            self.log.exception(f"Could not set up PostgreSQL. Exiting...")
            self.log.exception(format_error(e))
            return await asyncio.sleep(3600)
        else:
            async with self.db.aquire() as connection:
                await Table.create_tables(connection)

            for guild in await Config.fetchall():
                if guild.blacklisted:
                    self.guilds_to_leave.append(guild.guild_id)
                    continue
                self.config_cache[guild.guild_id] = {
                    "prefixes": guild.prefixes,
                    "logging_channel": self.get_channel(guild.logging_channel),
                    "logged_events": guild.logged_events,
                }

            self.log.info("Database fully setup")

        self.session = aiohttp.ClientSession()
        print(f'Extensions to be loaded are {", ".join(map(str, self.initial_extensions))}')

        for extension in self.initial_extensions:
            self.load_extension(extension.name)
        self.load_extension("jishaku")

        await super().start(config.TOKEN)

    async def on_command(self, ctx: Context) -> None:
        self.log.debug(
            f"""
Author : {ctx.author!r} - {ctx.author.id}
Guild  : {ctx.guild.name if ctx.guild else 'DMS'} {f'- {ctx.guild.id}' if ctx.guild else ''}
Channel: {(ctx.channel.name if ctx.guild else 'DMS')!r} {f'- {ctx.channel.id}' if ctx.guild else ''}
Message: {ctx.message.clean_content!r}"
"""
        )

    async def on_ready(self) -> None:
        if not self.first_ready:
            return

        for guild in self.guilds_to_leave:
            await self.get_guild(guild).leave()

        self.owner = (await self.application_info()).owner
        print(
            f"Logged in as: {self.user.name} V.{__version__} - {self.user.id} -- "
            f"Version: {discord.__version__} of Discord.py"
        )
        self.log.info(f"Logged in as: {self.user.name} V.{__version__} - {self.user.id}")
        self.log.info(f"Version: {discord.__version__} of Discord.py")
        self.first_ready = False

    async def close(self):
        self.log.info("About to close the DB")
        await self.db.close()
        self.log.info("About to close the ClientSession")
        await self.session.close()
        self.log.info("About to close the bot")
        await super().close()
