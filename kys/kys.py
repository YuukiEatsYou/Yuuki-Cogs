from redbot.core import commands
import discord

class KysCog(commands.Cog):
    """Responds with a GIF when !kys is used"""

    def __init__(self, bot):
        self.bot = bot
        self.gif_url = "https://media1.tenor.com/m/znYZvCPVkPQAAAAC/galaxy-angel-mint-blancmanche.gif"  # REPLACE WITH ACTUAL GIF URL

    @commands.command()
    async def kys(self, ctx):
        """Sends a GIF response"""
        try:
            embed = discord.Embed(color=await ctx.embed_color())
            embed.set_image(url=self.gif_url)
            await ctx.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("GIF failed to load :(")

# Setup function required by Red
async def setup(bot):
    await bot.add_cog(KysCog(bot))
