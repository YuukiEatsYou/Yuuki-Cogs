import discord
from redbot.core import commands, Config

class WordFilter(commands.Cog):
    """Automatically delete messages containing filtered words"""

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

        # Get filtered words for this guild
        blacklist = await self.config.guild(message.guild).blacklist()

        # Check if message contains any filtered word (case-insensitive)
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
    async def wordfilter(self, ctx):
        """Manage filtered words for auto-deletion"""
        pass

    @wordfilter.command(name="add")
    async def wordfilter_add(self, ctx, *, word: str):
        """Add a word to the filter"""
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            if any(w.lower() == word.lower() for w in blacklist):
                await ctx.send(f"`{word}` is already in the word filter.")
                return
            blacklist.append(word)

        await ctx.send(f"Added `{word}` to the word filter.")

    @wordfilter.command(name="remove", aliases=["rm", "delete"])
    async def wordfilter_remove(self, ctx, *, word: str):
        """Remove a word from the filter"""
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            original_length = len(blacklist)
            # Case-insensitive removal
            blacklist[:] = [w for w in blacklist if w.lower() != word.lower()]

            if len(blacklist) == original_length:
                await ctx.send(f"`{word}` was not found in the word filter.")
                return

        await ctx.send(f"Removed `{word}` from the word filter.")

    @wordfilter.command(name="list")
    async def wordfilter_list(self, ctx):
        """List all filtered words"""
        blacklist = await self.config.guild(ctx.guild).blacklist()

        if not blacklist:
            await ctx.send("The word filter is empty.")
            return

        formatted_list = "\n".join(f"• {word}" for word in blacklist)
        embed = discord.Embed(
            title="Filtered Words",
            description=formatted_list,
            color=await ctx.embed_color()
        )
        await ctx.send(embed=embed)

    @wordfilter.command(name="clear")
    @commands.admin_or_permissions(administrator=True)
    async def wordfilter_clear(self, ctx):
        """Clear all words from the filter (with confirmation)"""
        # Create confirmation message
        embed = discord.Embed(
            title="⚠️ Confirm Clear",
            description="This will remove **ALL** words from the filter!\nAre you sure?",
            color=0xFFCC4D
        )
        confirm_msg = await ctx.send(embed=embed)

        # Add reactions
        await confirm_msg.add_reaction("✅")  # Check mark
        await confirm_msg.add_reaction("❌")  # X mark

        # Wait for reaction
        def check(reaction, user):
            return (
                user == ctx.author and
                reaction.message.id == confirm_msg.id and
                str(reaction.emoji) in ["✅", "❌"]
            )

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
        except TimeoutError:
            await confirm_msg.delete()
            return

        # Process reaction
        if str(reaction.emoji) == "✅":
            await self.config.guild(ctx.guild).blacklist.set([])
            await ctx.send("✅ All words have been removed from the filter.")
        else:
            await ctx.send("❌ Clear operation cancelled.")

        try:
            await confirm_msg.delete()
        except discord.NotFound:
            pass

async def setup(bot):
    await bot.add_cog(WordFilter(bot))
