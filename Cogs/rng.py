import discord
import sr_api
import random

from io import BytesIO

from discord.ext import commands

client = sr_api.Client()


class RNG(commands.Cog):
    """These are commands from Some Random API"""

    def __init__(self, bot):
        self.bot = bot
        self.animals = ['cat', 'dog', 'koala', 'fox', 'birb', 'red_panda', 'panda', 'racoon', 'kangaroo']
        self._8ball_responses = ['It is certain.', 'It is decidedly so.', 'Without a doubt.', 'Yes - definitely.',
                                 'You may rely on it.', 'As I see it, yes.', 'Most likely.', 'Outlook good.', 'Yes.',
                                 'Signs point to yes.', 'Reply hazy, try again.', 'Ask again later.',
                                 'Better not tell you now.', 'Cannot predict now.', 'Concentrate and ask again.',
                                 "Don't count on it.", 'My reply is no.', 'My sources say no.', 'Outlook not so good.',
                                 'Very doubtful.', 'Ya like jazz? I do!']
        self.hug_images = ['https://media.tenor.com/images/c5a29b75582f26c28f5d271384f673ad/tenor.gif',
                     'https://media.tenor.com/images/9164f10a0dbbf7cdb6aeb46184b16365/tenor.gif',
                     'https://media.tenor.com/images/564eac526a8af795c90ce5985904096e/tenor.gif',
                     'https://media.tenor.com/images/4d5a77b99ab86fc5e9581e15ffe34b5e/tenor.gif',
                     'https://media.tenor.com/images/afbc39fcc4cbe67d9622f657d60d41cf/tenor.gif',
                     'https://media.tenor.com/images/5d5565fe47af258d83b4caa2a668ccfa/tenor.gif',
                     'https://media.tenor.com/images/4edcfcfa004403f844494025c5bf83da/tenor.gif',
                     'https://media.tenor.com/images/c3759877cdcb86e25a1d305d5ac6fe4d/tenor.gif',
                     'https://media.tenor.com/images/adbb48575b54edaabd7383010bc2510a/tenor.gif',
                     'https://tenor.com/view/dog-hug-bff-bestfriend-friend-gif-9512793',
                     'https://tenor.com/view/hugday-gif-4954554',
                     'https://tenor.com/view/big-hero6-baymax-feel-better-hug-hugging-gif-4782499',
                     'https://tenor.com/view/hug-your-cat-day-hug-cat-gif-8723720',
                     'https://media.tenor.com/images/adbb48575b54edaabd7383010bc2510a/tenor.gif',
                     'https://cdn.discordapp.com/attachments/448285120634421278/633527959092854807/boy_oh_boy_i_love_hugs.jpg']
        self.hug_hugs = ['(っ´▽｀)っ', '🤗', '⊂((・▽・))⊃', '＼(^o^)／', 'd=(´▽｀)=b', '⊂(◉‿◉)つ', '⊂（♡⌂♡）⊃',
                         '⊂( ◜◒◝ )⊃', '(づ｡◕‿‿◕｡)づ', '(づ￣ ³￣)づ', '(っ˘̩╭╮˘̩)っ', '⁽₍੭ ՞̑◞ළ̫̉◟՞̑₎⁾੭', '(੭ु｡╹▿╹｡)੭ु⁾⁾',
                         '(*´σЗ`)σ', '(っ´∀｀)っ', 'c⌒っ╹v╹ )っ', '(σ･з･)σ', '(੭ु´･ω･`)੭ु⁾⁾', '(oﾟ▽ﾟ)o','༼つ ் ▽ ் ༽つ',
                         '༼つ . •́ _ʖ •̀ . ༽つ', '╏つ ͜ಠ ‸ ͜ಠ ╏つ', '༼ つ ̥◕͙_̙◕͖ ͓༽つ', '༼ つ ◕o◕ ༽つ', '༼ つ ͡ ͡° ͜ ʖ ͡ ͡° ༽つ',
                         '(っಠ‿ಠ)っ', '༼ つ ◕_◕ ༽つ', 'ʕっ•ᴥ•ʔっ', '༼ つ ▀̿_▀̿ ༽つ', 'ʕ ⊃･ ◡ ･ ʔ⊃', '╏つ” ⊡ 〜 ⊡ ” ╏つ',
                         '(⊃｡•́‿•̀｡)⊃', '(っ⇀⑃↼)っ', '(.づ◡﹏◡)づ.', '(.づσ▿σ)づ.',' (っ⇀`皿′↼)っ', '(.づ▣ ͜ʖ▣)づ.',
                         '(つ ͡° ͜ʖ ͡°)つ', '(⊃ • ʖ̫ • )⊃', '(っ・∀・）っ', '(つ´∀｀)つ', '(っ*´∀｀*)っ', '(つ▀¯▀)つ',
                         '(つ◉益◉)つ', '(> ^_^ )>']
        self.ewan_images = ['https://i.pinimg.com/originals/4c/47/b9/4c47b9d5a2460f8a803a4535493a027c.gif',
                            'https://media.giphy.com/media/l3fZCIWuhobBy9eo0/giphy.gif',
                            'https://media2.giphy.com/media/l1Ku2UzLA5v7NhB28/giphy.gif',
                            'https://media1.giphy.com/media/1oJLpejP9jEvWQlZj4/giphy.gif',
                            'https://media1.giphy.com/media/KOVlHmbBA09XO/source.gif', 'https://i.gifer.com/S3tC.gif',
                            'https://i2.wp.com/metro.co.uk/wp-content/uploads/2019/08/PRI_82268727.jpg',
                            'https://i0.wp.com/metro.co.uk/wp-content/uploads/2019/10/PRI_91187240-e1572348269658.jpg',
                            'https://media.tenor.com/images/7d9dd76a1cce503c11188668c797e602/tenor.gif',
                            'https://media1.tenor.com/images/faaf8f6e28e459299caea7a751361439/tenor.gif?itemid=13545825',
                            'https://media.tenor.com/images/57f0b6be7d013823a24e091d9b29f4ef/tenor.gif',
                            'https://media.tenor.com/images/1313730fd103b01208539932c33fc3ab/tenor.gif',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684600011227156/tenor_12.gif',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684600442978314/starwars-revengeofthesith-obiwan-transport.jpg',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684600442978315/2019.08.15-07.16-boundingintocomics-5d55af99379cf.png',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684601055477770/2015StarWarsGallery_CaptainPanaka_ObiWanKenobi_Ewan_131115.jpg',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684628515586114/dims.jpeg',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684629069365288/2019-08-16-image-6.jpg',
                            'https://cdn.discordapp.com/attachments/620050263503536161/661684629668888616/mcgregor.jpg']
        self.ewan_quotes = ['Why do I get the feeling you\'re going to be the death of me?',
                            'These aren\'t the droids you\'re looking for.',
                            'Use the Force, Luke.', 'The Force will be with you, always.',
                            'That\'s no moon. It\'s a space station.', 'The Force is what gives a Jedi his power.',
                            'Why do I get the feeling that we\'ve picked up another pathetic life form?',
                            'I felt a great disturbance in the Force', 'Your eyes can deceive you; don\'t trust them.',
                            'I have a bad feeling about this.', 'In my experience, there\'s no such thing as luck.',
                            'Why hello there']

    async def cog_check(self, ctx):
        return True

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

    @commands.command(name='8ball')
    async def _8ball(self, ctx, *, question: commands.clean_content()):
        await ctx.send(f'Question: {question}'
                       f'\nAnswer: {random.choice(self._8ball_responses)}')

    @commands.command(aliases=['obi-wan'])
    async def ewan(self, ctx):
        """Someone need some ewan appreciation"""
        quote = random.choice(self.ewan_quotes)
        gif = random.choice(self.ewan_images)
        embed = discord.Embed(title=quote, color=discord.Colour.gold())
        embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.command()
    async def hug(self, ctx, huggie: discord.Member, *, note=None):
        """Someone need some love?
        eg. {prefix}hug @Gobot1234#2435 mmmmmh notes"""
        hugger = ctx.author

        if huggie.bot:
            response = random.choice(['You can\'t hug a bot :(', 'Imagine how cold they are'])
            await ctx.send(response)
        elif huggie == hugger:
            response = random.choice(['That\'s kind of sad ngl :(', 'Come on that\'s gotta feel weird', 'Get a room'])
            await ctx.send(response)
        else:
            gif = random.choice(self.hug_images)
            embed = discord.Embed(title=f"You have received a hug from {hugger.display_name} (っ´▽｀)っ", color=0xffd1dc)
            embed.set_image(url=gif)
            if note:
                embed.add_field(name='A note was enclosed', value=note, inline=False)
            await huggie.send(embed=embed)
            await ctx.send(f'> Hugged {huggie.display_name} {random.choice(self.hug_hugs)}')


def setup(bot):
    bot.add_cog(RNG(bot))
    bot.log.info('Loaded RNG cog')

