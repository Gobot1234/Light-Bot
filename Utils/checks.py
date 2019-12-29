from discord.ext.commands import CommandError


def prefix(ctx):
    # select ctx.guild.id return prefix
    pass


def colour_good(ctx):
    # select ctx.guild.id return colour
    pass


def colour_bad(ctx):
    # select ctx.guild.id return colour
    pass


def colour_neutral(ctx):
    # select ctx.guild.id return colour
    pass


def is_guild_owner(ctx):
    if ctx.author == ctx.guild.owner:
        return True
    else:
        raise NotGuildOwner(f'You are not the owner of this guild contact {ctx.guild.owner} if a command needs to be performed')


def is_agsb_guild(ctx):
    if ctx.guild.id == 376064130118844416:
        return True
    else:
        raise NotAGSBSever('You are not in the AGSB server so this command cannot be used')


class NotGuildOwner(CommandError):
    """Custom Exception class for Guild Owner Commands"""


class NotAGSBSever(CommandError):
    """Custom Exception class to check if its the AGSB server"""
