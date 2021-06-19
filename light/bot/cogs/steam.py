from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, NamedTuple, NoReturn, Optional, TypedDict

import discord
from discord.ext import commands, tasks
from humanize import naturaltime
from jishaku.functools import executor_function

# from matplotlib import pyplot as plt
# from matplotlib.figure import figaspect
from steam import Clan, Enum, FetchedGame, User
from steam.models import URL, api_route

from light.db import SteamService

from . import Cog, group
from .utils.context import Context

if TYPE_CHECKING:
    from light import Light


class UserStatsDataPoint(NamedTuple):
    timestamp_ms: int
    count: int


class GameServersStatus(TypedDict):
    class App(TypedDict):  # type: ignore
        version: int
        timestamp: int
        time: str

    app: App

    class Services(TypedDict):  # type: ignore
        class Enum(Enum, str):  # type: ignore
            normal = "normal"
            offline = "offline"
            idle = "idle"

        SessionsLogon: Enum
        SteamCommunity: Enum
        IEconItems: Enum
        Leaderboards: Enum

    services: Services

    class DataCenterInfo(TypedDict):  # type: ignore
        class Capacity(Enum, str):  # type: ignore
            full = "full"

        capacity: Capacity

        class Load(Enum, str):  # type: ignore
            idle = "idle"
            low = "low"
            medium = "medium"
            high = "high"
            overload = "overload"  # TODO what is this really?

        load: Load

    datacenters: dict[str, DataCenterInfo]

    class MatchMaking(TypedDict):  # noqa
        class Scheduler(Enum, str):  # noqa
            normal = "normal"

        scheduler: Scheduler
        online_servers: int
        online_players: int
        searching_players: int

    matchmaking: MatchMaking


class Steam(Cog):
    """The category for all steam related commands."""

    def __init__(self, bot: Light):
        super().__init__(bot)

        self.get_status.start()

    def cog_unload(self):
        self.get_status.cancel()

    def missing_argument(self, ctx: Context) -> NoReturn:  # once the defaults pr gets merged this can be removed
        raise commands.MissingRequiredArgument(ctx.current_parameter)

    @group(case_insensitive=True)
    async def steam(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @steam.command(name="user")
    async def steam_user(self, ctx: Context, user: Optional[User] = None):
        """Show some basic info on a steam user"""
        user = user or await ctx.user
        if user is None:
            self.missing_argument(ctx)

        friends, games, is_banned = await asyncio.gather(user.friends(), user.games(), user.is_banned())
        embed = discord.Embed(timestamp=user.created_at, colour=ctx.colour.steam)
        embed.set_author(name=user.name, url=user.community_url)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="64 bit ID:", value=user.id64)
        embed.add_field(name="Friends:", value=len(friends))
        embed.add_field(name="Games:", value=len(games))
        embed.add_field(name="Status:", value=user.state.name)
        embed.add_field(name="Is Banned:", value=is_banned)
        if user.game:
            embed.add_field(name="Currently playing:", value=user.game)
        embed.set_footer(text="Account created on")
        await ctx.send(embed=embed)

    @steam.command(name="clan")
    async def steam_clan(self, ctx: Context, clan: Clan):
        embed = discord.Embed(timestamp=clan.created_at, colour=ctx.colour.steam)
        embed.set_author(name=clan.name, url=clan.community_url)
        embed.set_thumbnail(url=clan.icon_url)
        embed.add_field(name="64 bit ID:", value=clan.id64)
        embed.add_field(name="Members:", value=clan.member_count)
        embed.add_field(name="Game:", value=clan.game)
        embed.set_footer(text="Clan created on")
        await ctx.send(embed=embed)

    @steam_clan.error
    @steam_user.error
    async def on_steam_subcommand_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            return await ctx.send(str(error))
        raise error

    @steam.command(name="game")
    async def steam_game(self, ctx: Context, *, game: FetchedGame = None):
        if game is None:
            user = await ctx.user
            if user is not None:
                game = user.game
        if game is None:
            self.missing_argument(ctx)
        embed = discord.Embed(timestamp=game.created_at, colour=ctx.colour.steam)
        embed.set_author(name=game.title, url=game.url)
        embed.set_thumbnail(url=game.logo_url)
        embed.add_field(name="ID:", value=game.id)
        embed.add_field(name="Description:", value=game.description)
        embed.add_field(name="Is free:", value=str(game.is_free()).lower())
        embed.add_field(name="Developed by:", value=", ".join(game.developers))
        embed.add_field(name="Published by:", value=", ".join(game.publishers))
        embed.set_footer(text="Game created on")
        return await ctx.send(embed=embed)

    @steam.command(name="stats", aliases=["status", "s"])
    async def steam_stats(self, ctx: Context):
        (recent,) = await SteamService.fetch(order_by=(SteamService.created_at, "DESC"), limit=1)
        embed = discord.Embed(colour=ctx.colour.steam)
        file = discord.File("steam_status.png")
        embed.set_author(
            name=(
                f"Steam Stats: {'fully operational' if recent.percent_up >= 80 else 'potentially unstable'} "
                f"{'👍' if recent.percent_up >= 80 else '👎'}"
            ),
            icon_url=ctx.emoji.steam.url,
            url="https://steamstat.us",
        )

        embed.add_field(name="Services:", value="\n".join(recent.service_info))
        embed.add_field(name="Games:", value="\n".join(recent.game_info))
        embed.add_field(name="Current players:", value="\n".join(recent.online_info), inline=False)
        embed.set_image(url="attachment://graph.png")
        await ctx.send(embed=embed, file=file)

    @executor_function
    def create_stats_graph(self, times: list[datetime], percentages: list[float]) -> None:
        plt.style.use("dark_background")
        w, h = figaspect(1 / 3)
        fig, ax = plt.subplots(figsize=(w, h))
        ax.grid(linestyle="-", linewidth="0.5", color="white")

        plt.setp(plt.plot(list(reversed(times)), percentages, linewidth=4), color=str(Context.colour.steam))

        plt.title(f"Steam CM status over the last {naturaltime(times[0])[:-4]}", size=20)
        plt.axis([None, None, 0, 100])
        plt.xlabel("Time (Month-Day Hour)", fontsize=20)
        plt.ylabel("Uptime (%)", fontsize=20)

        plt.tight_layout(h_pad=20, w_pad=20)
        plt.savefig("steam_status.png", format="png", transparent=True)

    @tasks.loop(minutes=1)
    async def get_status(self) -> None:
        await self.bot.client.wait_until_ready()
        now = discord.utils.utcnow()

        online_count_resp, server_status_resp = await asyncio.gather(
            self.bot.session.get(URL.STORE / "stats" / "userdata.json"),
            self.bot.session.get(
                api_route("ICSGOServers_730/GetGameServersStatus") % {"key": self.bot.client.http.api_key},
            ),
            return_exceptions=False,
        )

        if online_count_resp.status == 200:
            data: list[UserStatsDataPoint] = (await online_count_resp.json())[0]["data"]
            online_count = data[0][1]
        else:
            online_count = -1

        if server_status_resp.status == 200:
            server_status: GameServersStatus = (await server_status_resp.json())["result"]
            number_up = sum(
                server["load"] != GameServersStatus.DataCenterInfo.Load.overload
                for server in server_status["datacenters"].values()
            )
            percentage_up = round(number_up / len(server_status["datacenters"]) * 100, 1)

        else:
            percentage_up = -1

        record = await SteamService.insert(
            created_at=now,
            percent_up=percentage_up,
            online_count=online_count,
            community_status=True,
            store_status=True,
            api_status=True,
            returning="*",
        )
        # await self.create_stats_graph(times)


def setup(bot: Light) -> None:
    bot.add_cog(Steam(bot))
