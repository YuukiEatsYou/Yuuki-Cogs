import random
import asyncio
from redbot.core import commands, bank
from redbot.core.utils.predicates import MessagePredicate

class RussianRoulette(commands.Cog):
    """Multiplayer Russian Roulette with economy integration"""

    def __init__(self, bot):
        self.bot = bot
        self.games = {}  # {guild_id: {players: [], pot: int, in_progress: bool}}
        self.join_lock = asyncio.Lock()

    @commands.command()
    @commands.guild_only()
    async def rrjoin(self, ctx):
        """Join Russian Roulette (10,000 credit entry)"""
        guild = ctx.guild
        entry_fee = 10000

        async with self.join_lock:
            # Initialize game state
            if guild.id not in self.games:
                self.games[guild.id] = {
                    "players": [],
                    "pot": 0,
                    "in_progress": False
                }

            game = self.games[guild.id]

            # Validation checks
            if game["in_progress"]:
                return await ctx.send("🚨 A game is in progress! Join the next round.")
            if ctx.author in game["players"]:
                return await ctx.send("⚠️ You're already in the lobby!")
            if len(game["players"]) >= 6:
                return await ctx.send("🔒 Lobby full! Use `!rrstart` to begin")

            # Bank check
            if not await bank.can_spend(ctx.author, entry_fee):
                return await ctx.send(f"❌ You need 10,000 credits! (Current: {await bank.get_balance(ctx.author)})")

            # Withdraw entry fee
            await bank.withdraw_credits(ctx.author, entry_fee)

            # Add player
            game["players"].append(ctx.author)
            game["pot"] += entry_fee
            await ctx.send(f"🔫 {ctx.author.mention} joined! Players: **{len(game['players'])}/6** | Pot: **{game['pot']:,} credits**")

            # Auto-start if full
            if len(game["players"]) == 6:
                await ctx.invoke(self.rrstart)

    @commands.command()
    @commands.guild_only()
    async def rrstart(self, ctx):
        """Start Russian Roulette with current players"""
        guild = ctx.guild
        try:
            game = self.games[guild.id]
        except KeyError:
            return await ctx.send("❌ No active lobby! Use `!rrjoin` first")

        if game["in_progress"]:
            return await ctx.send("🚨 Game already running!")
        if len(game["players"]) < 2:
            return await ctx.send("⚠️ Need at least 2 players!")

        # Game setup
        game["in_progress"] = True
        players = game["players"]
        bullet_count = random.randint(1, 5)
        random.shuffle(players)
        survivors = []

        # Show game start
        embed = discord.Embed(
            title="💀 RUSSIAN ROULETTE STARTING",
            color=0xff0000
        )
        embed.add_field(name="Players", value="\n".join(p.mention for p in players), inline=False)
        embed.add_field(name="Pot", value=f"{game['pot']:,} credits", inline=True)
        embed.add_field(name="Bullets", value=f"{bullet_count}/6", inline=True)
        await ctx.send(embed=embed)

        # Game sequence
        for player in players:
            await asyncio.sleep(2)

            # 1 in 6 chance per bullet
            if random.randint(1, 6) <= bullet_count:
                await ctx.send(f"💥 **BANG!** {player.mention} is eliminated!")
            else:
                await ctx.send(f"✅ *click* {player.mention} survives!")
                survivors.append(player)

        # Payouts
        await asyncio.sleep(1)
        if survivors:
            winnings = game["pot"] // len(survivors)
            for player in survivors:
                await bank.deposit_credits(player, winnings)
            await ctx.send(f"🎉 **{len(survivors)} SURVIVORS WIN!**\nEach receives **{winnings:,} credits**")
        else:
            await ctx.send("☠️ **NO SURVIVORS!** The house keeps the pot!")

        # Cleanup
        del self.games[guild.id]

    @rrstart.error
    async def rrstart_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            await ctx.send("⚠️ Error starting game. Resetting lobby...")
            try:
                del self.games[ctx.guild.id]
            except KeyError:
                pass
