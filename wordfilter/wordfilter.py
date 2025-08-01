import discord
from redbot.core import commands, Config
import unicodedata

class WordFilter(commands.Cog):
    """Automatically delete messages containing filtered words"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=7345167902)
        default_guild = {
            "blacklist": []
        }
        self.config.register_guild(**default_guild)

        # Warn if normalization might not work perfectly
        bot.logger.info("WordFilter cog loaded. Note: Character normalization works best with Python 3.8+")

    def normalize_text(self, text):
        """Normalize text by converting to lowercase and removing diacritics"""
        # Normalize to NFKD form which separates characters and diacritics
        normalized = unicodedata.normalize('NFKD', text.lower())
        # Remove diacritical marks and convert to ASCII
        cleaned = ''.join(c for c in normalized if not unicodedata.combining(c))
        # Remove non-ASCII characters and return
        return cleaned.encode('ascii', 'ignore').decode('ascii')

    async def check_and_delete(self, message):
        """Check if a message contains filtered words and delete it if found"""
        # Ignore messages from bots, server owners, and DMs
        if (
            not message.guild or
            message.author.bot or
            message.author == message.guild.owner
        ):
            return False

        # Get filtered words for this guild
        blacklist = await self.config.guild(message.guild).blacklist()

        if not blacklist:
            return False

        # Normalize message content for better matching
        normalized_content = self.normalize_text(message.content)

        # Check if message contains any filtered word
        for bad_word in blacklist:
            # Normalize the bad word too for consistency
            normalized_bad = self.normalize_text(bad_word)
            if normalized_bad and normalized_bad in normalized_content:
                try:
                    await message.delete()
                    return True
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.Forbidden:
                    pass  # Missing permissions
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle new messages"""
        await self.check_and_delete(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Handle edited messages"""
        # Only process if content actually changed
        if before.content != after.content:
            await self.check_and_delete(after)

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def wordfilter(self, ctx):
        """Manage filtered words for auto-deletion"""
        pass

    @wordfilter.command(name="add")
    async def wordfilter_add(self, ctx, *, word: str):
        """Add a word to the filter"""
        if len(word) < 2:
            await ctx.send("Word must be at least 2 characters long.")
            return

        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            # Check both original and normalized versions for duplicates
            normalized_new = self.normalize_text(word)
            for existing in blacklist:
                if self.normalize_text(existing) == normalized_new:
                    await ctx.send(f"`{word}` or a similar variation is already in the word filter.")
                    return
            blacklist.append(word)

        await ctx.send(f"Added `{word}` to the word filter.")

    @wordfilter.command(name="remove", aliases=["rm", "delete"])
    async def wordfilter_remove(self, ctx, *, word: str):
        """Remove a word from the filter"""
        async with self.config.guild(ctx.guild).blacklist() as blacklist:
            original_length = len(blacklist)
            # Normalize the word to remove
            normalized_target = self.normalize_text(word)
            # Case-insensitive and accent-insensitive removal
            blacklist[:] = [w for w in blacklist
                           if self.normalize_text(w) != normalized_target]

            if len(blacklist) == original_length:
                await ctx.send(f"`{word}` or its variations were not found in the word filter.")
                return

        await ctx.send(f"Removed all variations of `{word}` from the word filter.")

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
