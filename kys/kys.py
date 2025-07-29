from redbot.core import commands
import discord
import random

class KysCog(commands.Cog):
    """Responds with a random GIF when !kys is used"""

    def __init__(self, bot):
        self.bot = bot
        # Add your DIRECT GIF URLs here
        self.gif_urls = [
            "https://media.tenor.com/fYukkGwzLbsAAAAd/tenor.gif",
            "https://media.tenor.com/znYZvCPVkPQAAAAd/tenor.gif",
            "https://media.tenor.com/EKk-IX4CAjYAAAAd/tenor.gif",
            "https://media.tenor.com/eohEkLqD9AgAAAAd/tenor.gif",
            "https://media.tenor.com/iRRfRNU7IGMAAAAd/tenor.gif",
            "https://media.tenor.com/0uGObo7wlWMAAAAd/tenor.gif",
            "https://media.tenor.com/eOvNbqR1ANUAAAAd/tenor.gif",
            "https://media.tenor.com/WZ2FaJkLXgcAAAAd/tenor.gif",
            "https://media.tenor.com/51ADdhpqqo4AAAAd/tenor.gif",
            "https://media.tenor.com/9IMZudPio58AAAAd/tenor.gif",
            # Add more GIFs as needed
        ]
    @commands.command()
    async def kys(self, ctx):

        # Select a random GIF
        gif_url = random.choice(self.gif_urls)

        # Send the GIF
        try:
            embed = discord.Embed(color=await ctx.embed_color())
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        except:
            await ctx.send("GIF failed to load 😢 Please check the URLs!")

async def setup(bot):
    await bot.add_cog(KysCog(bot))
