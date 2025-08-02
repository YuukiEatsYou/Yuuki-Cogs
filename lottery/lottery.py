import asyncio
import random
import discord
import time
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
            "cycle_minutes": 30, # Default 5 hours (300 minutes)
            "multiplier": 40,     # Default prize pool multiplier
            "next_draw": 0,      # Timestamp of next draw
            "banned_user": None, # ID of banned user
        }
        self.config.register_guild(**default_guild)
        self.lottery_task = None
        self.bot.loop.create_task(self.initialize_scheduler())

    async def initialize_scheduler(self):
        await self.bot.wait_until_ready()
        self.lottery_task = self.bot.loop.create_task(self.lottery_scheduler())

    def cog_unload(self):
        if self.lottery_task:
            self.lottery_task.cancel()

    async def lottery_scheduler(self):
        while True:
            data = await self.config.guild(self.bot.guilds[0]).all()
            next_draw = data["next_draw"]
            current_time = time.time()

            # Calculate wait time
            if next_draw <= current_time:
                # Draw immediately if we missed the schedule
                wait_time = 0
                await self.config.guild(self.bot.guilds[0]).next_draw.set(
                    current_time + data["cycle_minutes"] * 60
                )
            else:
                wait_time = next_draw - current_time

            await asyncio.sleep(wait_time)
            await self.draw_lottery(self.bot.guilds[0])

            # Set next draw time
            cycle_minutes = await self.config.guild(self.bot.guilds[0]).cycle_minutes()
            next_draw = time.time() + cycle_minutes * 60
            await self.config.guild(self.bot.guilds[0]).next_draw.set(next_draw)

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

        # Calculate time until next draw
        next_draw = await self.config.guild(ctx.guild).next_draw()
        time_left = next_draw - time.time()
        if time_left <= 0:
            time_str = "soon"
        else:
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            time_str = f"{hours} hours and {minutes} minutes"

        await ctx.send(
            f"Ticket purchased! Your numbers: `{ticket}`\n"
            f"Next draw in approximately {time_str}"
        )

    @commands.command()
    async def lottopool(self, ctx: commands.Context):
        """Show current lottery prize pool"""
        data = await self.config.guild(ctx.guild).all()
        base_pool = data["pool"]
        multiplier = data["multiplier"]
        total_pool = base_pool * multiplier

        tickets = data["tickets"]
        next_draw = data["next_draw"]
        time_left = next_draw - time.time()

        if time_left <= 0:
            time_str = "soon"
        else:
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            time_str = f"{hours}h {minutes}m"

        await ctx.send(
            f"**Base Pool:** {base_pool} credits\n"
            f"**Multiplier:** {multiplier}x\n"
            f"**Total Prize Pool:** {total_pool} credits\n"
            f"**Tickets Sold:** {len(tickets)}\n"
            f"**Next Draw:** {time_str}"
        )

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

    @lottoset.command()
    async def cycle(self, ctx: commands.Context, minutes: int):
        """Set draw cycle length in minutes (applies next cycle)"""
        if minutes < 1:
            return await ctx.send("Cycle must be at least 1 minute")
        await self.config.guild(ctx.guild).cycle_minutes.set(minutes)
        await ctx.send(f"Draw cycle set to {minutes} minutes. Will apply after current cycle.")

    @lottoset.command()
    async def multiplier(self, ctx: commands.Context, multiplier: int):
        """Set prize pool multiplier (e.g., 10 for 10x)"""
        if multiplier < 1:
            return await ctx.send("Multiplier must be at least 1")
        await self.config.guild(ctx.guild).multiplier.set(multiplier)
        await ctx.send(f"Prize pool multiplier set to {multiplier}x")

    @lottoset.command()
    async def banwinner(self, ctx: commands.Context, user: discord.User):
        """Prevent a user from winning the lottery (stealth mode)"""
        await self.config.guild(ctx.guild).banned_user.set(user.id)
        await ctx.send(f"{user.mention} has been secretly banned from winning! 🤫")

    @lottoset.command()
    async def unbanwinner(self, ctx: commands.Context):
        """Remove win ban from a user"""
        await self.config.guild(ctx.guild).banned_user.set(None)
        await ctx.send("Win ban has been removed!")

    async def draw_lottery(self, guild: discord.Guild):
        data = await self.config.guild(guild).all()
        if not data["tickets"]:
            # Reset timer if no tickets
            next_draw = time.time() + data["cycle_minutes"] * 60
            await self.config.guild(guild).next_draw.set(next_draw)
            return

        # Apply multiplier to prize pool
        base_pool = data["pool"]
        multiplier = data["multiplier"]
        prize_pool = base_pool * multiplier

        # Generate base winning numbers
        base_winning_numbers = [random.randint(0, 9) for _ in range(5)]
        winning_numbers = base_winning_numbers.copy()

        # Check if we need to modify winning numbers for banned user
        banned_user_id = data["banned_user"]
        banned_has_ticket = banned_user_id and str(banned_user_id) in data["tickets"]
        modified = False

        if banned_has_ticket:
            banned_ticket = data["tickets"][str(banned_user_id)]
            # Create a copy to modify
            winning_numbers = base_winning_numbers.copy()

            # For each position where banned user would win, modify that number
            for i in range(5):
                if banned_ticket[i] == winning_numbers[i]:
                    # Modify this number to prevent win
                    winning_numbers[i] = (winning_numbers[i] + 1) % 10
                    modified = True

        # Check all tickets against the final winning numbers
        winners = []  # (user_id, match_count, ticket)
        for user_id, ticket in data["tickets"].items():
            matches = sum(1 for i in range(5) if ticket[i] == winning_numbers[i])
            if matches > 0:
                winners.append((int(user_id), matches, ticket))

        total_wins = sum(match_count for _, match_count, _ in winners)

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
        leftover = base_pool - (total_payout // multiplier)  # Revert multiplier for storage

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

        # Format winning numbers (always show final numbers)
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

        # Get next cycle time for footer
        cycle_minutes = await self.config.guild(guild).cycle_minutes()
        hours = cycle_minutes // 60
        minutes = cycle_minutes % 60
        footer = f"Next draw in {hours} hours {minutes} minutes"

        embed.add_field(
            name="Prize Pool Breakdown",
            value=(
                f"**Base Pool:** {base_pool} credits\n"
                f"**Multiplier:** {multiplier}x\n"
                f"**Total Pool:** {prize_pool} credits\n"
                f"**Paid Out:** {total_payout} credits\n"
                f"**Carry Over:** {leftover} credits"
            )
        )

        embed.set_footer(text=footer)
        await channel.send(embed=embed)

def setup(bot: Red):
    bot.add_cog(Lottery(bot))
