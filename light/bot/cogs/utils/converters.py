from __future__ import annotations

import difflib
import re
from typing import ClassVar, TypeVar

import jishaku.codeblocks
import steam
from discord.ext import commands
from discord.utils import get
from steam.models import URL

from light.db import SteamUser

from .context import Context

T_co = TypeVar("T_co", covariant=True)


class TypeHintConverter(commands.Converter[T_co]):
    converter_for: ClassVar[type[T_co]]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.converter_for: type = cls.__orig_bases__[0].__args__[0]
        commands.converter.CONVERTER_MAPPING[cls.converter_for] = cls


class SteamUserConverter(TypeHintConverter[steam.User]):
    async def convert(self, ctx: Context, argument: str) -> steam.User:
        if argument.startswith("<@") and argument.endswith(">"):
            try:
                user = await commands.UserConverter().convert(ctx, argument)
            except commands.UserNotFound:
                raise

            user_record = await SteamUser.fetch_row(id=user.id)
            user = await ctx.bot.client.fetch_user(user_record.id64)
            if user:
                return user
            raise commands.BadArgument(f"I couldn't find a matching steam user for {argument!r}")

        try:
            user = await ctx.bot.client.fetch_user(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument, ctx.bot.session)
            if steam_id is None:
                raise commands.BadArgument(f"I couldn't find a matching ID or URL for {argument!r}")
            user = await ctx.bot.client.fetch_user(steam_id)

        if user is None:
            raise commands.BadArgument(f"I couldn't find a matching steam user for {argument!r}")
        return user


class SteamClanConverter(TypeHintConverter[steam.Clan]):
    async def convert(self, ctx: Context, argument: str) -> steam.Clan:
        try:
            clan = await ctx.bot.client.fetch_clan(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument, ctx.bot.session)
            if steam_id is None:
                raise commands.BadArgument(f"I couldn't find a matching ID or URL for {argument!r}")
            clan = await ctx.bot.client.fetch_clan(steam_id)

        if clan is None:
            raise commands.BadArgument(f"I couldn't find a matching steam clan for {argument!r}")
        return clan


class SteamGameConverter(TypeHintConverter[steam.FetchedGame]):
    async def convert(self, ctx: Context, argument: str) -> steam.FetchedGame:
        try:
            id = int(argument)
        except ValueError:
            resp = await ctx.bot.session.get(
                URL.STORE
                / "search"
                / "results"
                % {
                    "start": 0,
                    "count": 20,
                    "infinite": 0,
                    "json": "true",
                    "term": argument,
                }
            )
            data = await resp.json()
            games = []
            for game in data["items"]:
                try:
                    game = steam.Game(id=re.findall(r"steam/apps/(\d*)/", game["logo"])[0], title=game["name"])
                    games.append(game)
                except IndexError:
                    pass  # not an app

            if game_title := difflib.get_close_matches(argument, [game.title for game in games], n=1, cutoff=0.75):
                game = get(games, title=game_title[0])
                id = game.id
            elif not (
                id := {  # can't handle acronyms
                    "csgo": 730,
                    "cs-go": 730,
                    "tf2": 440,
                    "dota": 570,
                    "dota2": 570,
                }.get(argument.lower())
            ):
                raise commands.BadArgument(f"I couldn't find a matching steam game for {argument!r}")

        game = await ctx.bot.client.fetch_game(id)
        if game is None:
            raise commands.BadArgument(f"I couldn't find a matching steam game for {argument!r}")
        return game


class CodeBlockConverter(TypeHintConverter[jishaku.codeblocks.Codeblock]):
    async def convert(self, ctx: Context, argument: str) -> jishaku.codeblocks.Codeblock:
        return jishaku.codeblocks.codeblock_converter(argument)
