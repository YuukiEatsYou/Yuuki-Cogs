import random
import asyncio
import discord
from redbot.core import commands, bank
from redbot.core.errors import BalanceTooHigh

class RussianRoulette(commands.Cog):
    """Multiplayer Russian Roulette with proper economy handling"""

    ENTRY_FEE = 100000

    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.join_lock = asyncio.Lock()

    async def get_member(self, guild: discord.Guild, user_id: int) -> discord.Member:
        """Get member from guild or fetch globally if needed"""
        member = guild.get_member(user_id)
        if member:
            return member

        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            try:
                return await self.bot.fetch_user(user_id)
            except discord.NotFound:
                return None

    async def refund_player(self, ctx, guild: discord.Guild, user_id: int):
        """Safely refund a player"""
        try:
            member = await self.get_member(guild, user_id)
            if member:
                await bank.deposit_credits(member, self.ENTRY_FEE)
                return True
        except (BalanceTooHigh, ValueError, TypeError, AttributeError):
            pass
        return False

    async def refund_lobby(self, ctx, guild_id: int):
        """Refund all players in a lobby"""
        if guild_id not in self.games:
            return [], []

        game = self.games[guild_id]
        guild = self.bot.get_guild(guild_id)
        refunded = []
        failed = []

        for user_id, user_name in list(game["players"].items()):
            if await self.refund_player(ctx, guild, user_id):
                refunded.append(f"<@{user_id}> ({user_name})")
            else:
                failed.append(f"<@{user_id}> ({user_name})")

        del self.games[guild_id]
        return refunded, failed

    @commands.command()
    @commands.guild_only()
    async def rrjoin(self, ctx):
        """Join Russian Roulette (10,000 credit entry)"""
        guild = ctx.guild
        user = ctx.author
        entry_fee = self.ENTRY_FEE

        async with self.join_lock:
            # Initialize game state
            if guild.id not in self.games:
                self.games[guild.id] = {
                    "players": {},
                    "pot": 0,
                    "in_progress": False
                }

            game = self.games[guild.id]

            # Validation checks
            if game["in_progress"]:
                return await ctx.send("🚨 A game is in progress! Join the next round.")
            if user.id in game["players"]:
                return await ctx.send("⚠️ You're already in the lobby!")
            if len(game["players"]) >= 6:
                return await ctx.send("🔒 Lobby full! Use `!rrstart` to begin")

            # Bank check
            try:
                balance = await bank.get_balance(user)
                if balance < entry_fee:
                    return await ctx.send(f"❌ You need {entry_fee} credits! (You have: {balance})")

                await bank.withdraw_credits(user, entry_fee)
            except Exception as e:
                return await ctx.send(f"❌ Bank error: {str(e)}")

            # Add player
            game["players"][user.id] = user.display_name
            game["pot"] += entry_fee
            await ctx.send(
                f"🔫 {user.mention} joined! "
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
        guild = ctx.guild

        # Lobby check
        if guild.id not in self.games or not self.games[guild.id]["players"]:
            return await ctx.send("❌ No active lobby! Use `!rrjoin` first")

        game = self.games[guild.id]

        if game["in_progress"]:
            return await ctx.send("🚨 Game already running!")

        if len(game["players"]) < 2:
            refunded, failed = await self.refund_lobby(ctx, guild.id)
            msg = "⚠️ Need at least 2 players! "
            if refunded:
                msg += f"Refunded: {', '.join(refunded)}. "
            if failed:
                msg += f"Failed to refund: {', '.join(failed)}"
            return await ctx.send(msg)

        try:
            # Game setup
            game["in_progress"] = True
            player_data = list(game["players"].items())
            bullet_count = random.randint(1, 5)
            random.shuffle(player_data)
            survivors = []

            # Show game start
            embed = discord.Embed(
                title="💀 RUSSIAN ROULETTE STARTING",
                color=0xff0000,
                description=(
                    f"**Pot:** {game['pot']:,} credits\n"
                    f"**Bullets:** {bullet_count}/6\n"
                    f"**Players:** {len(player_data)}"
                )
            )

            await ctx.send(embed=embed)

            # Game sequence
            for user_id, display_name in player_data:
                await asyncio.sleep(2)

                if random.randint(1, 6) <= bullet_count:  # Player shot
                    await ctx.send(f"💥 **BANG!** <@{user_id}> ({display_name}) is eliminated!")
                else:  # Player survives
                    await ctx.send(f"✅ *click* <@{user_id}> ({display_name}) survives!")
                    survivors.append((user_id, display_name))

            # Payouts
            await asyncio.sleep(1)
            if survivors:
                winnings = game["pot"] // len(survivors)
                winners_msg = []
                failed_msg = []

                for user_id, display_name in survivors:
                    try:
                        member = await self.get_member(guild, user_id)
                        if member:
                            await bank.deposit_credits(member, winnings)
                            winners_msg.append(f"<@{user_id}> ({display_name})")
                        else:
                            raise ValueError("Player not found")
                    except Exception as e:
                        failed_msg.append(f"<@{user_id}> - {str(e)}")

                result = f"🎉 **{len(survivors)} SURVIVOR(S) WIN!**\nEach receives **{winnings:,} credits**"
                if winners_msg:
                    result += f"\nWinners: {', '.join(winners_msg)}"
                if failed_msg:
                    result += f"\n❌ Failed payments: {', '.join(failed_msg)}"

                await ctx.send(result)
            else:
                await ctx.send("☠️ **NO SURVIVORS!** The house keeps the pot!")

        except Exception as e:
            await ctx.send(f"⚠️ Game error: {str(e)}. Refunding all players...")
            refunded, failed = await self.refund_lobby(ctx, guild.id)
            if refunded:
                await ctx.send(f"✅ Refunded: {', '.join(refunded)}")
            if failed:
                await ctx.send(f"❌ Failed to refund: {', '.join(failed)}")
        finally:
            # Cleanup
            if guild.id in self.games:
                del self.games[guild.id]

    @commands.command()
    @commands.guild_only()
    async def rrcancel(self, ctx):
        """Cancel the current lobby and refund players"""
        guild = ctx.guild
        if guild.id not in self.games:
            return await ctx.send("❌ No active lobby!")

        refunded, failed = await self.refund_lobby(ctx, guild.id)
        msg = "✅ Lobby canceled. "
        if refunded:
            msg += f"Refunded: {', '.join(refunded)}. "
        if failed:
            msg += f"Failed to refund: {', '.join(failed)}"
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(RussianRoulette(bot))
