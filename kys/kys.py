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
        # Delete the user's command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass  # Bot doesn't have message delete permissions

        # Send the GIF response
        await ctx.send(self.gif_url)

# Setup function required by Red
async def setup(bot):
    await bot.add_cog(KysCog(bot))
