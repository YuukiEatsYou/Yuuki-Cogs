import json
import secrets
import time
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import discord
from redbot.core import commands, bank, data_manager
from redbot.core.errors import BankError

class ReferralSystem(commands.Cog):
    """Referral system with one-time use codes and credit rewards"""

    def __init__(self, bot):
        self.bot = bot
        self.data_path = Path(data_manager.cog_data_path(self)) / "referral_data.json"
        self.data = self._load_data()
        self.lock = asyncio.Lock()  # For safe data writing

    def _load_data(self):
        """Load referral data from JSON file"""
        if not self.data_path.exists():
            return {"referral_codes": {}, "claimed_users": {}}

        try:
            with open(self.data_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"referral_codes": {}, "claimed_users": {}}

    async def _save_data(self):
        """Save data to JSON file with thread lock"""
        async with self.lock:
            with open(self.data_path, "w") as f:
                json.dump(self.data, f, indent=4)

    def _generate_code(self) -> str:
        """Create a unique 8-character referral code"""
        while True:
            code = secrets.token_urlsafe(6)[:8].upper()
            if code not in self.data["referral_codes"]:
                return code

    @commands.command()
    async def refer(self, ctx):
        """Generate your personal referral code"""
        user_id = str(ctx.author.id)
        new_code = self._generate_code()

        self.data["referral_codes"][new_code] = {
            "referrer": user_id,
            "created_at": time.time(),
            "used": False
        }

        await self._save_data()
        await ctx.send(
            f"**Your referral code: `{new_code}`**\n"
            "Share this with friends! When they join and use "
            f"`!claimreferral {new_code}`, you'll both get rewards!"
        )

    @commands.command()
    @commands.guild_only()
    async def claimreferral(self, ctx, code: str):
        """Claim a referral reward using a referral code"""
        user_id = str(ctx.author.id)
        code = code.strip().upper()

        # Check if user already claimed a referral
        if user_id in self.data["claimed_users"]:
            return await ctx.send("❌ You've already claimed a referral reward!")

        # Validate code
        code_data = self.data["referral_codes"].get(code)
        if not code_data:
            return await ctx.send("❌ Invalid referral code!")
        if code_data["used"]:
            return await ctx.send("❌ This code has already been used!")

        # Prevent self-claiming
        if user_id == code_data["referrer"]:
            return await ctx.send("❌ You can't claim your own referral code!")

        # Verify join time (must be within last 24 hours)
        join_time = ctx.author.joined_at.replace(tzinfo=timezone.utc)
        time_since_join = datetime.now(timezone.utc) - join_time

        if time_since_join > timedelta(hours=24):
            return await ctx.send(
                "❌ You joined more than 24 hours ago!\n"
                "Referral rewards can only be claimed by new members."
            )

        # Process rewards
        reward = 10000  # Credits to award
        referrer = ctx.guild.get_member(int(code_data["referrer"]))

        try:
            # Award new user
            await bank.deposit_credits(ctx.author, reward)

            # Award referrer if still in server
            if referrer:
                await bank.deposit_credits(referrer, reward)
        except BankError as e:
            return await ctx.send(f"❌ Banking error: {e}")

        # Update tracking
        code_data["used"] = True
        self.data["claimed_users"][user_id] = code
        await self._save_data()

        # Send confirmation
        await ctx.send(
            f"🎉 Success! {ctx.author.mention} received **{reward} credits**.\n"
            f"Referrer {referrer.mention if referrer else 'someone'} also received **{reward} credits**!"
        )

    @claimreferral.error
    async def claimreferral_error(self, ctx, error):
        """Handle missing code argument"""
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please specify a referral code! Example: `!claimreferral CODE123`")
        elif isinstance(error, commands.CommandInvokeError) and "NoneType" in str(error):
            await ctx.send("❌ Could not verify your join time. Please contact an admin.")

async def setup(bot):
    await bot.add_cog(ReferralSystem(bot))
