from redbot.core import commands
import discord
import re
import random

class KysCog(commands.Cog):
    """Responds with a random GIF when !kys is used"""

    def __init__(self, bot):
        self.bot = bot
        # Add your Tenor GIF links here (share URLs)
        self.tenor_urls = [
            "https://tenor.com/view/kms-im-gonna-gus-gusjohnson-gif-18194767",
            "https://tenor.com/view/byuntear-skull-kms-gif-1200559089239851574",
            "https://tenor.com/view/suicide-kms-gif-4481206",
            # Add more GIFs as needed
        ]

    def convert_tenor_to_gif(self, url):
        """Converts Tenor share URL to direct GIF URL"""
        match = re.search(r"https?://(?:www\.)?tenor\.com/view/(?:[\w-]+-)?(\d+)", url)
        if match:
            gif_id = match.group(1)
            return f"https://media.tenor.com/{gif_id}/tenor.gif"
        return url  # Fallback to original URL

    @commands.command()
    async def kys(self, ctx):
        """Sends a random GIF response"""
        # Delete the user's command message
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass  # Gracefully fail if no permissions

        # Select a random GIF and convert it
        random_gif = random.choice(self.tenor_urls)
        gif_url = self.convert_tenor_to_gif(random_gif)

        # Send the GIF
        try:
            embed = discord.Embed(color=await ctx.embed_color())
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        except discord.HTTPException:
            await ctx.send("GIF failed to load 😢 Please check the links!")

async def setup(bot):
    await bot.add_cog(KysCog(bot))
