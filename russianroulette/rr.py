import random
import asyncio
import discord
from redbot.core import commands, bank
from redbot.core.utils.predicates import MessagePredicate

class RussianRoulette(commands.Cog):
    """Multiplayer Russian Roulette with economy integration"""

    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.join_lock = asyncio.Lock()

    async def refund_lobby(self, guild_id):
        """Refund all players in a lobby"""
        if guild_id not in self.games:
            return

        game = self.games[guild_id]
        for user_id in list(game["players"]):
            try:
                await bank.deposit_credits(user_id, 10000)
            except:
                pass  # User might have left server

        del self.games[guild_id]

    @commands.command()
    @commands.guild_only()
    async def rrjoin(self, ctx):
        """Join Russian Roulette (10,000 credit entry)"""
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        entry_fee = 10000

        async with self.join_lock:
            # Initialize game state
            if guild_id not in self.games:
                self.games[guild_id] = {
                    "players": {},
                    "pot": 0,
                    "in_progress": False
                }

            game = self.games[guild_id]

            # Validation checks
            if game["in_progress"]:
                return await ctx.send("🚨 A game is in progress! Join the next round.")
            if user_id in game["players"]:
                return await ctx.send("⚠️ You're already in the lobby!")
            if len(game["players"]) >= 6:
                return await ctx.send("🔒 Lobby full! Use `!rrstart` to begin")

            # Bank check
            if not await bank.can_spend(ctx.author, entry_fee):
                return await ctx.send(f"❌ You need 10,000 credits! (Current: {await bank.get_balance(ctx.author)})")

            # Withdraw entry fee
            try:
                await bank.withdraw_credits(ctx.author, entry_fee)
            except:
                return await ctx.send("❌ Failed to withdraw credits. Contact bot owner.")

            # Add player
            game["players"][user_id] = ctx.author.display_name
            game["pot"] += entry_fee
            await ctx.send(
                f"🔫 {ctx.author.mention} joined! "
                f"Players: **{len(game['players'])}/6** | "
                f"Pot: **{game['pot']:,} credits**\n"
                f"Use `{ctx.prefix}rrstart` to begin or wait for more players"
            )

            # Auto-start if full
            if len(game["players"]) == 6:
                await ctx.invoke(self.rrstart)

    @commands.command()
    @commands.guild_only()
    async def rrstart(self, ctx):
        """Start Russian Roulette with current players"""
        guild_id = ctx.guild.id

        # Lobby check
        if guild_id not in self.games or not self.games[guild_id]["players"]:
            return await ctx.send("❌ No active lobby! Use `!rrjoin` first")

        game = self.games[guild_id]

        if game["in_progress"]:
            return await ctx.send("🚨 Game already running!")

        if len(game["players"]) < 2:
            await self.refund_lobby(guild_id)
            return await ctx.send("⚠️ Need at least 2 players! Refunded all entries.")

        try:
            # Game setup
            game["in_progress"] = True
            player_ids = list(game["players"].keys())
            display_names = list(game["players"].values())
            bullet_count = random.randint(1, 5)
            random.shuffle(player_ids)
            survivors = []

            # Show game start
            embed = discord.Embed(
                title="💀 RUSSIAN ROULETTE STARTING",
                color=0xff0000
            )
            embed.add_field(
                name="Players",
                value="\n".join(f"<@{id}>" for id in player_ids),
                inline=False
            )
            embed.add_field(name="Pot", value=f"{game['pot']:,} credits", inline=True)
            embed.add_field(name="Bullets", value=f"{bullet_count}/6", inline=True)
            await ctx.send(embed=embed)

            # Game sequence
            for user_id in player_ids:
                await asyncio.sleep(2)
                display_name = game["players"][user_id]

                # 1 in 6 chance per bullet
                if random.randint(1, 6) <= bullet_count:
                    await ctx.send(f"💥 **BANG!** <@{user_id}> ({display_name}) is eliminated!")
                else:
                    await ctx.send(f"✅ *click* <@{user_id}> ({display_name}) survives!")
                    survivors.append(user_id)

            # Payouts
            await asyncio.sleep(1)
            if survivors:
                winnings = game["pot"] // len(survivors)
                for user_id in survivors:
                    try:
                        await bank.deposit_credits(user_id, winnings)
                    except:
                        await ctx.send(f"⚠️ Failed to pay <@{user_id}>. Contact bot owner.")

                await ctx.send(
                    f"🎉 **{len(survivors)} SURVIVOR(S) WIN!**\n"
                    f"Each receives **{winnings:,} credits**"
                )
            else:
                await ctx.send("☠️ **NO SURVIVORS!** The house keeps the pot!")

        except Exception as e:
            await ctx.send(f"⚠️ Game error: {str(e)}. Refunding all players...")
            await self.refund_lobby(guild_id)
        finally:
            # Cleanup
            if guild_id in self.games:
                del self.games[guild_id]

    @commands.command()
    @commands.guild_only()
    async def rrcancel(self, ctx):
        """Cancel the current lobby and refund players"""
        guild_id = ctx.guild.id
        if guild_id not in self.games:
            return await ctx.send("❌ No active lobby!")

        await self.refund_lobby(guild_id)
        await ctx.send("✅ Lobby canceled. All players refunded 10,000 credits!")

async def setup(bot):
    await bot.add_cog(RussianRoulette(bot))
