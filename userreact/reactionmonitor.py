from redbot.core import commands, Config
from redbot.core.bot import Red
import discord

class ReactionMonitor(commands.Cog):
    """Auto-reacts to messages from a specific user"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_guild(
            target_user_id=None,
            emoji_data=None
        )

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def setreacttarget(self, ctx, user: discord.User, emoji: str):
        """Set the target user and reaction emoji for this server.

        Example:
        `[p]setreacttarget @Username 👍`
        `[p]setreacttarget @Username :custom_emoji:`
        """
        # Try to convert to PartialEmoji if custom emoji
        try:
            partial_emoji = await commands.PartialEmojiConverter().convert(ctx, emoji)
            emoji_data = {
                "id": partial_emoji.id,
                "name": partial_emoji.name,
                "animated": partial_emoji.animated
            }
            display_emoji = str(partial_emoji)
        except commands.BadArgument:
            # Treat as unicode emoji
            emoji_data = {"unicode": emoji}
            display_emoji = emoji

        await self.config.guild(ctx.guild).target_user_id.set(user.id)
        await self.config.guild(ctx.guild).emoji_data.set(emoji_data)

        await ctx.send(f"✅ Now reacting to {user.mention}'s messages with {display_emoji}")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def clearreacttarget(self, ctx):
        """Clear the reaction settings for this server"""
        await self.config.guild(ctx.guild).target_user_id.set(None)
        await self.config.guild(ctx.guild).emoji_data.set(None)
        await ctx.send("✅ Reaction settings cleared")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None:  # Ignore DMs
            return
        if message.author.bot:  # Ignore bots
            return

        guild = message.guild
        config = await self.config.guild(guild).all()

        if not config["target_user_id"] or not config["emoji_data"]:
            return

        if message.author.id != config["target_user_id"]:
            return

        emoji_data = config["emoji_data"]

        try:
            # Handle custom emoji
            if "id" in emoji_data:
                emoji = self.bot.get_emoji(emoji_data["id"])
                if not emoji:
                    # Try to fetch partial emoji if not in cache
                    emoji = discord.PartialEmoji(
                        name=emoji_data["name"],
                        id=emoji_data["id"],
                        animated=emoji_data["animated"]
                    )
            # Handle unicode emoji
            else:
                emoji = emoji_data["unicode"]

            await message.add_reaction(emoji)
        except discord.HTTPException as e:
            print(f"Failed to add reaction: {e}")

async def setup(bot: Red):
    await bot.add_cog(ReactionMonitor(bot))
