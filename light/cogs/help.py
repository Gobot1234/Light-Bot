from __future__ import annotations
import difflib
from datetime import datetime, timedelta
from io import BytesIO
from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands, menus
from humanize import naturaltime
from jishaku.functools import executor_function
from matplotlib import pyplot as plt
from matplotlib.figure import figaspect

from .utils.context import Context
from .utils.converters import UserConverter
from .utils.formats import human_join

if TYPE_CHECKING:
    from .. import Light


class HelpPages(menus.ListPageSource):
    def format_page(self, menu: HelpMenu, page: discord.Embed):
        return page


class HelpMenu(menus.MenuPages):
    def __init__(self, entries: list[discord.Embed]):
        super().__init__(source=HelpPages(entries, per_page=1))


class EmbedHelpCommand(commands.HelpCommand):
    context: Context
    COLOUR = discord.Colour.blurple()

    def get_ending_note(self) -> str:
        return f"Use {self.clean_prefix}{self.invoked_with} [command] for more info on a command."

    def get_command_signature(self, command: commands.Command) -> str:
        return f"{command.qualified_name} {command.signature}"

    async def send_bot_help(self, mapping: dict[commands.Cog, list[commands.Command]]) -> None:
        entries = []
        for cog, commands in mapping.items():
            name = getattr(cog, "qualified_name", None) or "No Category"
            embed = discord.Embed(title=f"{name}'s commands", colour=self.COLOUR)
            filtered = await self.filter_commands(commands, sort=True)
            if filtered:
                value = "\n".join(f"**{c.name}**: {c.short_doc}" for c in commands)
                if cog and cog.description:
                    value = f"{cog.description}\n\n{value}"

                embed.add_field(name="\u200b", value=value)

            embed.set_footer(text=self.get_ending_note())
            entries.append(embed)
        await HelpMenu(entries).start(self.context)

    async def send_cog_help(self, cog):
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", colour=self.COLOUR)
        if cog.description:
            embed.description = cog.description

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            embed.add_field(name=self.get_command_signature(command), value=command.short_doc or "...", inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(title=command.qualified_name, colour=self.COLOUR)
        if command.help:
            embed.description = command.help

        if isinstance(command, commands.Group):
            filtered = await self.filter_commands(command.commands, sort=True)
            for command in filtered:
                embed.add_field(
                    name=self.get_command_signature(command), value=command.short_doc or "...", inline=False
                )

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    send_group_help = send_command_help

    async def send_error_message(self, error):
        ...

    async def command_not_found(self, string: str) -> None:
        ctx = self.context
        command_names = [command.name for command in ctx.bot.commands]
        close_commands = difflib.get_close_matches(string, command_names, n=2, cutoff=0.75)
        joined = "\n".join(f"`{command}`" for command in close_commands)

        embed = discord.Embed(
            title="Error!",
            description=(
                f"**Error 404:** Command or category {string!r} not found\nPerhaps you meant:\n{joined}"
                if joined
                else f"**Error 404:** Command or category {string!r} not found"
            ),
            colour=discord.Colour.red(),
        )
        await self.get_destination().send(embed=embed)


class Help(commands.Cog):
    """Need help? Try these with <@630008145162272778> help <command>"""

    def __init__(self, bot: Light):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = EmbedHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a member's avatar with links to download/view in higher quality"""
        member = member or ctx.author
        embed = discord.Embed(
            title=f"{member.display_name}'s avatar",
            description=(
                f"[PNG]({member.avatar_url_as(format='png')}) | "
                f"[JPEG]({member.avatar_url_as(format='jpg')}) | "
                f"[WEBP]({member.avatar_url_as(format='webp')})"
            ),
            colour=discord.Colour.blurple(),
        )
        if member.is_avatar_animated():
            embed.description += f" | [GIF]({member.avatar_url_as(format='gif')})"
        embed.set_author(name=member.display_name, icon_url=member.avatar_url)
        embed.set_image(url=member.avatar_url_as(format="gif" if member.is_avatar_animated() else "png"))
        await ctx.send(embed=embed)

    @commands.command(aliases=["member"])
    async def user(self, ctx: Context, user: discord.User = None):
        """Simple user info"""
        user = user or ctx.author

        voice_perms = [
            "deafen_members",
            "move_members",
            "mute_members",
            "priority_speaker",
            "speak",
            "stream",
            "use_voice_activation",
            "connect",
        ]
        key_to_emoji = {
            "online": ctx.emoji.online,
            "idle": ctx.emoji.idle,
            "dnd": ctx.emoji.dnd,
            "offline": ctx.emoji.offline,
        }

        perms = [
            f"{ctx.emoji.tick} {perm.title()}"
            for perm, val in sorted(dict(user.permissions_in(ctx.channel)).items())
            if val and perm not in voice_perms
        ]
        perms_denied = [
            f"{ctx.emoji.cross} {perm.title()}"
            for perm, val in sorted(dict(user.permissions_in(ctx.channel)).items())
            if not val and perm not in voice_perms
        ]
        perms = "\n".join(perms).replace("_", " ").replace("Tts", "TTS") if perms else "None"
        perms_denied = "\n".join(perms_denied).replace("_", " ").replace("Tts", "TTS") if perms_denied else "None"

        embed = discord.Embed(title=f"Info on {user}", colour=user.colour)
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="ID:", value=user.id)
        embed.add_field(name=f"{user.display_name} created their account:", value=naturaltime(user.created_at))
        if isinstance(user, discord.Member):
            embed.add_field(name=f"{user.display_name} joined this guild:", value=naturaltime(user.joined_at))

            embed.add_field(
                name=f'{user.display_name} has these permission{"s" if len(perms) != 1 else ""} in this channel:',
                value=perms if "Administrator" not in perms else "All as they are Admin",
            )
            embed.add_field(
                name=f'{user.display_name} has these permission{"s" if len(perms) != 1 else ""} denied in this channel:',
                value=perms_denied,
            )
            if user.premium_since:
                embed.add_field(
                    name=f"{user.display_name} has been boosting since:", value=naturaltime(user.premium_since)
                )

            embed.add_field(
                name=f"Roles ({len(user.roles) - 1})",
                value=human_join(
                    [role.mention for role in sorted(user.roles[1:], reverse=True, key=lambda r: r.position)],
                    final="and",
                )
                if len(user.roles) != 0
                else "None",
                inline=False,
            )
            embed.add_field(
                name="Status:",
                value=(
                    f"{key_to_emoji[str(user.status)]} "
                    f'{str(user.status).title().replace("Dnd", "Do Not Disturb")}\n'
                ),
            )
        await ctx.send(embed=embed)

    @commands.command()
    async def steam_user(self, ctx: commands.Context, user: UserConverter):
        """Show some basic info on a steam user"""
        if user is None:
            return await ctx.send("User not found")

        embed = discord.Embed(description=user.name, timestamp=user.created_at)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="64 bit ID:", value=str(user.id64))
        embed.add_field(name="Currently playing:", value=str(user.game) or "Nothing")
        embed.add_field(name="Friends:", value=str(len(await user.friends())))
        embed.add_field(name="Games:", value=str(len(await user.games())))
        embed.set_footer(text="Account created on")
        await ctx.send(f"Info on {user.name}", embed=embed)

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

    @commands.command(aliases=["steamstats", "steamstatus", "ss"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def steam_stats(self, ctx: Context):
        """Get Steam's current status"""
        async with ctx.typing():
            r = await self.bot.session.get("https://crowbar.steamstat.us/gravity.json")
            if r.status != 200:
                return await ctx.send("Could not fetch Steam stats. Try again later.")

            data = await r.json()
            graph = await self.gen_steam_stats_graph(data)

            code_to_city = {
                "ams": "Amsterdam",
                "atl": "Atlanta",
                "bom": "Mumbai",
                "can": "Guangzhou",
                "dxb": "Dubai",
                "eat": "Moses Lake",
                "fra": "Frankfurt",
                "gru": "Sao Paulo",
                "hkg": "Hong Kong",
                "iad": "Sterling",
                "jnb": "Johannesburg",
                "lax": "Los Angeles",
                "lhr": "London",
                "lim": "Lima",
                "lux": "Luxembourg",
                "maa": "Chennai",
                "mad": "Madrid",
                "man": "Manilla",
                "okc": "Oklahoma City",
                "ord": "Chicago",
                "par": "Paris",
                "scl": "Santiago",
                "sea": "Seattle",
                "sgp": "Singapore",
                "sha": "Shanghai",
                "sto": "Stockholm",
                "syd": "Sydney",
                "tsn": "Tianjin",
                "tyo": "Tokyo",
                "vie": "Vienna",
                "waw": "Warsaw",
            }
            code_to_game = {
                "artifact": "Artifact",
                "csgo": "CS-GO",
                "dota2": "DOTA 2",
                "tf2": "TF2",
                "underlords": "Underlords",
            }
            code_to_service = {"cms": "Steam CMs", "community": "Community", "store": "Store", "webapi": "Web API"}
            code_to_gamers = {
                "ingame": "In-game",
                "online": "Online",
            }

            cities = {
                code_to_city.get(service[0]): service[2] for service in data["services"] if code_to_city.get(service[0])
            }
            games = {
                code_to_game.get(service[0]): service[2] for service in data["services"] if code_to_game.get(service[0])
            }
            services = {
                code_to_service.get(service[0]): service[2]
                for service in data["services"]
                if code_to_service.get(service[0])
            }
            gamers = {
                code_to_gamers.get(service[0]): service[2]
                for service in data["services"]
                if code_to_gamers.get(service[0])
            }

            server_info = [
                f'{ctx.emoji.tick if country[1] == "OK" or float(country[1][:-1]) >= 80 else ctx.emoji.cross} '
                f'{country[0]} - {country[1] if country[1].split(".")[0].isdigit() else "100.0%"}'
                for country in sorted(cities.items(), key=lambda kv: (kv[0], kv[1]))
            ]
            game_info = [
                f'{ctx.emoji.tick if game[1] == "Normal" else ctx.emoji.cross} {game[0]} - {game[1]}'
                for game in sorted(games.items(), key=lambda kv: (kv[0], kv[1]))
            ]
            service_info = [
                f'{ctx.emoji.tick if service[1] == "Normal" or service[1].split()[0].split(".")[0].isdigit() else ctx.emoji.cross}'
                f" {service[0]} - {service[1]}"
                for service in sorted(services.items(), key=lambda kv: (kv[0], kv[1]))
            ]

            gamers = "\n".join(
                f"{gamer[0]} - {gamer[1]}" for gamer in sorted(gamers.items(), key=lambda kv: (kv[0], kv[1]))
            )

            services = "\n".join(service_info)
            embed = discord.Embed(colour=ctx.colour.steam)
            embed.set_author(
                name=(
                    f'Steam Stats: {"Fully operational" if data["online"] >= 70 else "Potentially unstable"} '
                    f'{"👍" if data["online"] >= 70 else "👎"}'
                ),
                icon_url="https://www.freeiconspng.com/uploads/steam-icon-19.png",
            )

            embed.description = f"{services}\n\n{gamers}"
            first = server_info[: len(server_info) // 2]
            second = server_info[len(server_info) // 2:]
            embed.add_field(name="CMs Servers:", value="\n".join(first))
            embed.add_field(name="\u200b", value="\n".join(second))
            embed.add_field(name="Games:", value="\n".join(game_info))
            embed.set_image(url="attachment://graph.png")
            await ctx.send(embed=embed, file=graph)


def setup(bot):
    bot.add_cog(Help(bot))
