from __future__ import annotations

import asyncio
import traceback
from datetime import datetime
from io import BytesIO
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING, Logger, LogRecord

import discord


class WebhookLogger(Logger):
    COLOURS = {
        CRITICAL: discord.Colour.dark_red(),
        ERROR: discord.Colour.red(),
        WARNING: discord.Colour.gold(),
        INFO: discord.Colour.green(),
        DEBUG: discord.Colour.light_grey(),
    }

    def __init__(self, webhook: discord.Webhook):
        super().__init__("light", level=DEBUG)
        self.webhook = webhook
        self.queue = asyncio.Queue[LogRecord]()

    def handle(self, record: LogRecord) -> None:
        self.queue.put_nowait(record)

    async def sender(self) -> None:
        while True:
            embeds = []
            files = []
            for record in [
                r
                for r in await asyncio.gather(
                    *(asyncio.wait_for(self.queue.get(), timeout=10) for _ in range(10)),
                    return_exceptions=True,
                )
                if isinstance(r, LogRecord)
            ]:  # gather up to 10 embeds for sending
                description = "\n".join(
                    [
                        f"```{'py' if record.exc_info else ''}",
                        record.msg,
                        *(traceback.format_exception(*record.exc_info) if record.exc_info else ()),
                        "```",
                    ]
                )
                embed = discord.Embed(
                    title=f"logging.{record.levelname} emitted in `{record.pathname}`",
                    colour=self.COLOURS[record.levelno],
                    timestamp=datetime.utcfromtimestamp(record.created),
                )
                if len(description) <= 2048:
                    embed.description = description
                    embeds.append(embed)
                else:
                    # too large to send as an embed description
                    error = "\n".join(traceback.format_exception(*record.exc_info) if record.exc_info else ())
                    files.append(discord.File(BytesIO(f"{record.msg}\n{error}".encode()), filename="error.py"))

            if embeds or files:
                await self.webhook.send(embeds=embeds, files=files)
