from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ... import Light


class WebhookLogger(Logger):
    COLOURS = {
        CRITICAL: discord.Colour.dark_red(),
        ERROR: discord.Colour.red(),
        WARNING: discord.Colour.gold(),
        INFO: discord.Colour.green(),
        DEBUG: discord.Colour.light_grey(),
    }

    def __init__(self, adapter: discord.AsyncWebhookAdapter):
        super().__init__("light", level=DEBUG)
        self.adapter = adapter
        self.queue: asyncio.Queue[LogRecord] = asyncio.Queue()

    @classmethod
    async def from_bot(cls, bot: Light) -> WebhookLogger:
        logger = cls(bot.webhook_adapter)
        asyncio.create_task(logger.sender())
        return logger

    def handle(self, record: LogRecord) -> None:
        self.queue.put_nowait(record)

    async def sender(self) -> None:
        while True:
            to_send = [
                r
                for r in await asyncio.gather(
                    *(asyncio.wait_for(self.queue.get(), timeout=10) for _ in range(5)),
                    return_exceptions=True,
                )
                if isinstance(r, LogRecord)
            ]  # gather up to 5 embeds for sending

            embeds = []

            for record in to_send:
                page = ["```py\n" if record.exc_info else "```"]
                if record.exc_info:
                    exc = traceback.format_exception(*record.exc_info)
                    page.append("\n".join(exc))

                page.append(record.msg)
                page.append("```")

                embed = discord.Embed(
                    title=f"logging.{record.levelname} emitted in `{record.pathname}`",
                    colour=self.COLOURS[record.levelno],
                    description="\n".join(page),
                    timestamp=datetime.utcfromtimestamp(record.created),
                )
                embeds.append(embed)

            if embeds:
                await self.adapter.webhook.send(embeds=embeds)
