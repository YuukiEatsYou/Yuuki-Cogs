from redbot.core import commands
import discord

class TutorialCog(commands.Cog):
    """Detailed tutorial commands for new users"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def tutorial(self, ctx):
        """Display a detailed server tutorial"""

        # Create main tutorial embed
        embed = discord.Embed(
            title="YuukiCoin Tutorial",
            description="Everything you need to know about YuukiCoins:",
            color=discord.Color.blue()
        )

        # Add command sections
        embed.add_field(
            name="Economy",
            value=(
                "`!bank balance` - Shows your YuukiCoin balance\n"
                "`!bank transfer <user> <amount>` - Send YuukiCoins to other users\n"
                "`!payday` - Use every hour to get 100 YuukiCoins\n"
                "`!leaderboard` - View the top users by YuukiCoins"
            ),
            inline=False
        )

        embed.add_field(
            name="Shop",
            value=(
                "`!shop` - view the item shop\n"
                "`!buy <item_id>` - buy items from the shop\n"
                "`!sell <item_id>` - sell items back to the shop\n"
                "`!inventory` - view your inventory\n"
                "`!item <item_id>` - view item details\n"
                "`!market` - view the marketplace\n"
                "`!buymarket <market_id>` - buy items from the marketplace\n"
                "`!sellmarket <market_id>` - sell items to the marketplace"            ),
            inline=False
        )

        embed.add_field(
            name="Games",
            value=(
                "`!slot <amount>` - Play slots game\n"
                "`!hol` - Play higher or lower\n"
                "`!combat` - Start a combat challenge\n"
                "`!heal` - Heal yourself for 100 YuukiCoins"
            ),
            inline=False
        )

        # Send tutorial embed
        await ctx.send(embed=embed)

# Cog setup function required by Red
async def setup(bot):
    await bot.add_cog(TutorialCog(bot))
