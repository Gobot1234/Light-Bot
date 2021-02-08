# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, NamedTuple, Union

import discord
from discord.ext import commands
from humanize import naturaltime
from jishaku.functools import executor_function
from matplotlib import pyplot as plt
from matplotlib.figure import figaspect

from . import Cog
from .utils.context import Context
from .utils.converters import SteamUser, SteamClan

if TYPE_CHECKING:
    from .. import Light


class ServiceInfo:
    def __init__(self, name: str, status: str):
        if status.endswith("%"):
            status = float(status[:-1])
        elif status.endswith("million"):
            pass
        elif "." in status:
            status = float(re.findall(r"(\d+\.\d+)", status)[0])
        elif status in ("OK", "Normal"):
            status = 100.0

        self.name = name
        self.status: Union[str, float] = status


class SteamStats(NamedTuple):
    service_info: list[str]
    game_info: list[str]
    online_info: list[str]
    is_stable: bool


class Steam(Cog):
    """The category for all steam related commands.

    Use {bot_mention}help steam for more info on these.
    """

    @commands.group(case_insensitive=True)
    async def steam(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @steam.command(name="user")
    async def steam_user(self, ctx: Context, user: SteamUser):
        """Show some basic info on a steam user"""
        friends, games, is_banned = await asyncio.gather(user.friends(), user.games(), user.is_banned())
        embed = discord.Embed(timestamp=user.created_at, colour=ctx.colour.steam)
        embed.set_author(name=user.name, url=user.community_url)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="64 bit ID:", value=user.id64)
        embed.add_field(name="Friends:", value=len(friends))
        embed.add_field(name="Games:", value=len(games))
        embed.add_field(name="Status:", value=user.state.name)
        embed.add_field(name="Is Banned:", value=is_banned)
        embed.add_field(name="Currently playing:", value=user.game or "Nothing")
        embed.set_footer(text="Account created on")
        await ctx.send(embed=embed)

    @steam_user.error
    async def on_steam_user_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            return await ctx.send("User not found")
        raise error

    @steam.command(name="clan")
    async def steam_clan(self, ctx: Context, clan: SteamClan):
        embed = discord.Embed(timestamp=clan.created_at, colour=ctx.colour.steam)
        embed.set_author(name=clan.name, url=clan.community_url)
        embed.set_thumbnail(url=clan.icon_url)
        embed.add_field(name="64 bit ID:", value=clan.id64)
        embed.add_field(name="Members:", value=clan.member_count)
        embed.add_field(name="Game:", value=clan.game)
        embed.set_footer(text="Clan created on")
        await ctx.send(embed=embed)

    @steam_clan.error
    async def on_steam_clan_error(self, ctx: Context, error: commands.CommandError):
        if isinstance(error, commands.BadArgument):
            return await ctx.send("Clan not found")
        raise error

    @executor_function
    def gen_steam_stats_graph(self, data: dict) -> discord.File:
        graph_data = data["graph"]
        steps = timedelta(milliseconds=graph_data["step"])
        timestamp = datetime.utcfromtimestamp(graph_data["start"] / 1000)
        plots = graph_data["data"]
        times = []

        for _ in plots:
            timestamp -= steps
            times.append(timestamp)

        plt.style.use("dark_background")
        w, h = figaspect(1 / 3)
        fig, ax = plt.subplots(figsize=(w, h))
        ax.grid(linestyle="-", linewidth="0.5", color="white")

        plt.setp(plt.plot(list(reversed(times)), plots, linewidth=4), color="#00adee")

        plt.title(f"Steam CM status over the last {naturaltime(timestamp)[:-4]}", size=20)
        plt.axis([None, None, 0, 100])
        plt.xlabel("Time (Month-Day Hour)", fontsize=20)
        plt.ylabel("Uptime (%)", fontsize=20)

        plt.tight_layout(h_pad=20, w_pad=20)
        buf = BytesIO()
        plt.savefig(buf, format="png", transparent=True)
        buf.seek(0)
        plt.close()
        return discord.File(buf, filename="graph.png")

    def map_steam_stats(self, data: dict) -> SteamStats:
        code_to_game = {
            "artifact": "Artifact",
            "csgo": "CS-GO",
            "dota2": "DOTA 2",
            "tf2": "TF2",
            "underlords": "Underlords",
        }
        code_to_service = {
            "cms": "Steam CMs",
            "community": "Community",
            "store": "Store",
            "webapi": "Web API",
        }
        code_to_gamers = {
            "ingame": "In-game",
            "online": "Online",
        }

        def gen_service_info(map_to: dict[str, str]) -> list[ServiceInfo]:
            return sorted(
                [
                    ServiceInfo(name=map_to[service[0]], status=service[2])
                    for service in data["services"]
                    if service[0] in map_to
                ],
                key=lambda service: service.name,
            )

        games = gen_service_info(code_to_game)
        services = gen_service_info(code_to_service)
        gamers = gen_service_info(code_to_gamers)

        e = Context.emoji
        return SteamStats(
            game_info=[
                f"{e.tick if game.status >= 80 else e.cross} {game.name} - "
                f"{'Normal' if game.status >= 80 else game.status}"
                for game in games
            ],
            service_info=[
                f"{e.tick if service.status >= 80 else e.cross} {service.name} - "
                f"{'Normal' if service.status >= 80 else service.status}"
                for service in services
            ],
            online_info=[f"{gamer.name} - {gamer.status}" for gamer in gamers],
            is_stable=data["online"] >= 80,
        )

    @steam.command(name="stats", aliases=["status", "s"])
    @commands.cooldown(1, 30, commands.BucketType.user)  # probably should add max_concurrency
    async def steam_stats(self, ctx: Context):
        """Get Steam's current status using https://steamstat.us."""
        async with ctx.typing():
            r = await self.bot.session.get("https://crowbar.steamstat.us/gravity.json")
            if r.status != 200:
                return await ctx.send("Could not fetch Steam stats. Try again later.")

            data = await r.json()
            graph: discord.File = await self.gen_steam_stats_graph(data)  # noqa
            steam_stats = self.map_steam_stats(data)

            embed = discord.Embed(colour=ctx.colour.steam)
            embed.set_author(
                name=(
                    f"Steam Stats: {'fully operational' if steam_stats.is_stable else 'potentially unstable'} "
                    f"{'👍' if steam_stats.is_stable else '👎'}"
                ),
                icon_url=ctx.emoji.steam.url,
                url="https://steamstat.us",
            )

            embed.add_field(name="Services:", value="\n".join(steam_stats.service_info))
            embed.add_field(name="Games:", value="\n".join(steam_stats.game_info))
            embed.add_field(name="Current players:", value="\n".join(steam_stats.online_info), inline=False)
            embed.set_image(url="attachment://graph.png")
            await ctx.send(embed=embed, file=graph)


def setup(bot: Light) -> None:
    bot.add_cog(Steam(bot))
