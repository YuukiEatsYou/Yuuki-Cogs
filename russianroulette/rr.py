import random
import asyncio
import discord
from redbot.core import commands, bank
from redbot.core.errors import BalanceTooHigh

class RussianRoulette(commands.Cog):
    """Multiplayer Russian Roulette with proper economy handling"""

    ENTRY_FEE = 10000

    def __init__(self, bot):
        self.bot = bot
        self.games = {}
        self.join_lock = asyncio.Lock()
        self.bank_cog = None

    async def get_bank_cog(self):
        """Safely get the bank cog instance"""
        if not self.bank_cog or not self.bank_cog.registered:
            self.bank_cog = self.bot.get_cog("Bank")
        return self.bank_cog

    async def refund_player(self, ctx, user_id: int):
        """Safely refund a player"""
        try:
            bank_cog = await self.get_bank_cog()
            if bank_cog:
                await bank_cog.deposit_credits(user_id, self.ENTRY_FEE)
                return True
        except (BalanceTooHigh, ValueError, TypeError):
            pass
        return False

    async def refund_lobby(self, ctx, guild_id: int):
        """Refund all players in a lobby"""
        if guild_id not in self.games:
            return

        game = self.games[guild_id]
        refunded = []
        failed = []

        for user_id in list(game["players"].keys()):
            if await self.refund_player(ctx, user_id):
                refunded.append(f"<@{user_id}>")
            else:
                failed.append(f"<@{user_id}>")

        del self.games[guild_id]
        return refunded, failed

    @commands.command()
    @commands.guild_only()
    async def rrjoin(self, ctx):
        """Join Russian Roulette (10,000 credit entry)"""
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        user_name = ctx.author.display_name

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
            try:
                balance = await bank.get_balance(ctx.author)
                if balance < self.ENTRY_FEE:
                    return await ctx.send(f"❌ You need {self.ENTRY_FEE} credits! (You have: {balance})")

                await bank.withdraw_credits(ctx.author, self.ENTRY_FEE)
            except Exception as e:
                return await ctx.send(f"❌ Bank error: {str(e)}")

            # Add player
            game["players"][user_id] = user_name
            game["pot"] += self.ENTRY_FEE
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
            refunded, failed = await self.refund_lobby(ctx, guild_id)
            msg = "⚠️ Need at least 2 players! "
            if refunded:
                msg += f"Refunded: {', '.join(refunded)}. "
            if failed:
                msg += f"Failed to refund: {', '.join(failed)}"
            return await ctx.send(msg)

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
                color=0xff0000,
                description=f"**Pot:** {game['pot']:,} credits\n**Bullets:** {bullet_count}/6"
            )

            players_list = "\n".join(
                f"<@{id}> - {name}"
                for id, name in zip(player_ids, display_names)
            )
            embed.add_field(name="Players", value=players_list, inline=False)
            await ctx.send(embed=embed)

            # Game sequence
            for user_id, display_name in zip(player_ids, display_names):
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
                        await bank.deposit_credits(user_id, winnings)
                        winners_msg.append(f"<@{user_id}> ({display_name})")
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
            refunded, failed = await self.refund_lobby(ctx, guild_id)
            if refunded:
                await ctx.send(f"✅ Refunded: {', '.join(refunded)}")
            if failed:
                await ctx.send(f"❌ Failed to refund: {', '.join(failed)}")
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

        refunded, failed = await self.refund_lobby(ctx, guild_id)
        msg = "✅ Lobby canceled. "
        if refunded:
            msg += f"Refunded: {', '.join(refunded)}. "
        if failed:
            msg += f"Failed to refund: {', '.join(failed)}"
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(RussianRoulette(bot))
