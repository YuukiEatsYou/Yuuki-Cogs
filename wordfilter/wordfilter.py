import discord
from redbot.core import commands, Config

class WordFilter(commands.Cog):
    """Automatically delete messages containing blacklisted words"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7345167902)
        default_guild = {
            "blacklist": []
        }
        self.config.register_guild(**default_guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from bots, server owners, and DMs
        if (
            not message.guild or
            message.author.bot or
            message.author == message.guild.owner
        ):
            return

        # Get blacklisted words for this guild
        blacklist = await self.config.guild(message.guild).blacklist()

        # Check if message contains any blacklisted word (case-insensitive)
        content_lower = message.content.lower()
        if any(bad_word.lower() in content_lower for bad_word in blacklist):
            try:
                await message.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except discord.Forbidden:
                pass  # Missing permissions

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def blacklist(self, ctx):
        """Manage blacklisted words"""
        pass

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx, *, word: str):
        """Add a word to the blacklist"""
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if any(w.lower() == word.lower() for w in blacklist):
                await ctx.send(f"`{word}` is already blacklisted.")
                return
            blacklist.append(word)

        await ctx.send(f"Added `{word}` to the blacklist.")

    @blacklist.command(name="remove", aliases=["rm", "delete"])
    async def blacklist_remove(self, ctx, *, word: str):
        """Remove a word from the blacklist"""
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            original_length = len(blacklist)
            # Case-insensitive removal
            blacklist[:] = [w for w in blacklist if w.lower() != word.lower()]

            if len(blacklist) == original_length:
                await ctx.send(f"`{word}` was not found in the blacklist.")
                return

        await ctx.send(f"Removed `{word}` from the blacklist.")

    @blacklist.command(name="list")
    async def blacklist_list(self, ctx):
        """List all blacklisted words"""
        blacklist = await self.config.guild(ctx.guild).blacklist()

        if not blacklist:
            await ctx.send("The blacklist is empty.")
            return

        formatted_list = "\n".join(f"• {word}" for word in blacklist)
        embed = discord.Embed(
            title="Blacklisted Words",
            description=formatted_list,
            color=await ctx.embed_color()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WordFilter(bot))
