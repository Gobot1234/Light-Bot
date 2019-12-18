import random
from io import BytesIO

from discord.ext import commands
import sr_api
import discord

client = sr_api.Client()


class Api(commands.Cog):
    """These are commands from Some Random API"""

    def __init__(self, bot):
        self.bot = bot
        self.animals = ['cat', 'dog', 'koala', 'fox', 'birb', 'red_panda', 'panda', 'racoon', 'kangaroo']

    @commands.command(aliases=['kitty', 'pussy'])
    async def cat(self, ctx, fact=None):
        """Get an image and optionally a fact about a cat"""
        await ctx.trigger_typing()
        image = await client.get_image('cat')
        file = discord.File(fp=BytesIO(await image.read()), filename="cat.jpg")

        embed = discord.Embed(title=':cat: Meowww..', url=image.url, color=discord.Colour.blurple())
        embed.set_image(url='attachment://cat.jpg')
        if fact is not None:
            fact = await client.get_fact('cat')
            embed.description = f'Cat fact: {fact}'
        await ctx.send(content=None, embed=embed, file=file)

    @commands.command(aliases=['doggo'])
    async def dog(self, ctx, fact=None):
        """Get an image and optionally a fact about a dog"""
        await ctx.trigger_typing()
        image = await client.get_image('dog')
        file = discord.File(fp=BytesIO(await image.read()), filename="dog.jpg")

        embed = discord.Embed(title=':dog: Woof..', url=image.url, color=discord.Colour.blurple())
        embed.set_image(url='attachment://dog.jpg')
        if fact is not None:
            fact = await client.get_fact('dog')
            embed.description = f'Dog fact: {fact}'
        await ctx.send(content=None, embed=embed, file=file)

    @commands.command()
    async def koala(self, ctx, fact=None):
        """Get an image and optionally a fact about a koala"""
        await ctx.trigger_typing()
        image = await client.get_image('koala')
        file = discord.File(fp=BytesIO(await image.read()), filename="koala.jpg")

        embed = discord.Embed(title=':koala: Koala bear..', url=image.url, color=discord.Colour.blurple())
        embed.set_image(url='attachment://koala.jpg')
        if fact is not None:
            fact = await client.get_fact('koala')
            embed.description = f'Koala fact: {fact}'
        await ctx.send(content=None, embed=embed, file=file)


def setup(bot):
    bot.add_cog(Api(bot))
