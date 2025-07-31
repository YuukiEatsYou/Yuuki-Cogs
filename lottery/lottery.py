import asyncio
import random
import discord
from redbot.core import commands, Config, bank
from redbot.core.bot import Red
from typing import Dict, List, Tuple, Optional

class Lottery(commands.Cog):
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "pool": 0,          # Current prize pool (credits)
            "tickets": {},       # {user_id: [n1, n2, n3, n4, n5]}
            "channel_id": None,  # Announcement channel ID
        }
        self.config.register_guild(**default_guild)
        self.lottery_task = self.bot.loop.create_task(self.lottery_scheduler())

    def cog_unload(self):
        self.lottery_task.cancel()

    async def lottery_scheduler(self):
        await self.bot.wait_until_ready()
        while True:
            await asyncio.sleep(5 * 3600)  # 5 hours
            for guild in self.bot.guilds:
                await self.draw_lottery(guild)

    @commands.command()
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def lottobuy(self, ctx: commands.Context):
        """Buy a lottery ticket for 5000 credits (1 per draw cycle)"""
        async with self.config.guild(ctx.guild).all() as data:
            user_id = str(ctx.author.id)

            # Check existing ticket
            if user_id in data["tickets"]:
                await ctx.send("You already have a ticket for this draw cycle!")
                return

            # Check balance
            if await bank.get_balance(ctx.author) < 5000:
                await ctx.send("You need 5000 credits to buy a ticket!")
                return

            # Deduct credits and add to pool
            await bank.withdraw_credits(ctx.author, 5000)
            data["pool"] += 5000

            # Generate ticket
            ticket = [random.randint(0, 9) for _ in range(5)]
            data["tickets"][user_id] = ticket

        await ctx.send(
            f"Ticket purchased! Your numbers: `{ticket}`\n"
            f"Next draw in approximately 5 hours"
        )

    @commands.command()
    async def lottopool(self, ctx: commands.Context):
        """Show current lottery prize pool"""
        pool = await self.config.guild(ctx.guild).pool()
        tickets = await self.config.guild(ctx.guild).tickets()
        await ctx.send(f"**Prize Pool:** {pool} credits\n**Tickets sold:** {len(tickets)}")

    @commands.group()
    @commands.admin_or_permissions(manage_guild=True)
    async def lottoset(self, ctx: commands.Context):
        """Lottery admin settings"""
        pass

    @lottoset.command()
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the lottery announcement channel"""
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"Lottery announcements will now be sent to {channel.mention}")

    async def draw_lottery(self, guild: discord.Guild):
        data = await self.config.guild(guild).all()
        if not data["tickets"]:
            return  # No active tickets

        # Generate winning numbers
        winning_numbers = [random.randint(0, 9) for _ in range(5)]
        winners = []  # (user_id, match_count, ticket)

        # Check tickets
        for user_id, ticket in data["tickets"].items():
            matches = sum(1 for i in range(5) if ticket[i] == winning_numbers[i])
            if matches > 0:
                winners.append((int(user_id), matches, ticket))

        total_wins = sum(match_count for _, match_count, _ in winners)
        prize_pool = data["pool"]

        # Calculate winnings
        payouts = {}
        if winners:
            if total_wins <= 5:
                per_win = int(prize_pool * 0.2)
                for user_id, match_count, _ in winners:
                    payout = match_count * per_win
                    payouts[user_id] = payouts.get(user_id, 0) + payout
            else:
                per_win = prize_pool // total_wins
                for user_id, match_count, _ in winners:
                    payout = match_count * per_win
                    payouts[user_id] = payouts.get(user_id, 0) + payout

            # Distribute winnings
            for user_id, amount in payouts.items():
                user = guild.get_member(user_id)
                if user:
                    await bank.deposit_credits(user, amount)

        # Calculate leftover
        total_payout = sum(payouts.values())
        leftover = prize_pool - total_payout

        # Save results
        await self.config.guild(guild).pool.set(leftover)
        await self.config.guild(guild).tickets.set({})

        # Send announcement
        channel_id = data["channel_id"]
        if not channel_id:
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="🎰 Lottery Draw Results 🎰",
            color=discord.Color.gold()
        )

        # Format winning numbers
        win_str = " ".join(str(n) for n in winning_numbers)
        embed.add_field(name="Winning Numbers", value=f"`{win_str}`", inline=False)

        # Format results
        if not winners:
            result = "No winning tickets! Prize pool carries over to next draw."
        else:
            result = []
            for user_id, match_count, ticket in winners:
                user = guild.get_member(user_id)
                ticket_str = " ".join(str(n) for n in ticket)
                payout = payouts.get(user_id, 0)
                result.append(
                    f"**{user.mention if user else 'Unknown'}** - "
                    f"`{ticket_str}` ({match_count}/5) - "
                    f"**{payout} credits**"
                )
            result = "\n".join(result)

        embed.add_field(
            name="Results",
            value=result or "No winners",
            inline=False
        )

        embed.add_field(
            name="Prize Pool",
            value=(
                f"**Current:** {prize_pool} credits\n"
                f"**Paid out:** {total_payout} credits\n"
                f"**Carry over:** {leftover} credits"
            )
        )

        embed.set_footer(text="Next draw in 5 hours")
        await channel.send(embed=embed)

def setup(bot: Red):
    bot.add_cog(Lottery(bot))
