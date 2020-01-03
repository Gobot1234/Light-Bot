from discord.ext.commands import CommandError


def is_guild_owner(ctx):
    if ctx.author == (ctx.guild.owner or ctx.bot.owner):
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
