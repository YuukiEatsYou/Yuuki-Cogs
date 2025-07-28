import discord
import asyncio
from datetime import datetime, timedelta
from dateutil.parser import parse
from redbot.core import commands, Config, bank
from typing import Literal

class BattlePass(commands.Cog):
    """Battle Pass system for daily rewards"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=987654321)

        default_global = {
            "price": 5000,
            "rewards": {}
        }

        default_user = {
            "battle_pass": {
                "active": False,
                "purchase_date": None,
                "last_claim": None,
                "days_claimed": 0
            }
        }

        self.config.register_global(**default_global)
        self.config.register_user(**default_user)

    async def get_currency_name(self, ctx):
        """Get currency name for the guild"""
        return await bank.get_currency_name(ctx.guild)

    async def get_shop_cog(self):
        """Get the shop cog instance"""
        return self.bot.get_cog("ShopSystem")

    @commands.group()
    async def battlepass(self, ctx):
        """Battle Pass commands"""
        pass

    @battlepass.command(name="buy")
    async def battlepass_buy(self, ctx):
        """Purchase the Battle Pass"""
        async with self.config.user(ctx.author).battle_pass() as bp:
            if bp["active"]:
                return await ctx.send("❌ You already have an active Battle Pass!")

            price = await self.config.price()
            currency_name = await self.get_currency_name(ctx)

            if await bank.get_balance(ctx.author) < price:
                return await ctx.send(
                    f"❌ You need {price} {currency_name} to buy the Battle Pass!"
                )

            await bank.withdraw_credits(ctx.author, price)
            bp["active"] = True
            bp["purchase_date"] = datetime.utcnow().isoformat()
            bp["last_claim"] = None
            bp["days_claimed"] = 0

        await ctx.send(
            f"✅ Successfully purchased the Battle Pass for {price} {currency_name}!\n"
            "Use `!battlepass claim` to claim your first reward."
        )

    @battlepass.command(name="claim")
    async def battlepass_claim(self, ctx):
        """Claim your daily Battle Pass reward"""
        async with self.config.user(ctx.author).battle_pass() as bp:
            # Check if active
            if not bp["active"]:
                return await ctx.send("❌ You don't have an active Battle Pass!")

            # Check if expired
            purchase_date = parse(bp["purchase_date"])
            if (datetime.utcnow() - purchase_date).days >= 30:
                bp["active"] = False
                return await ctx.send("❌ Your Battle Pass has expired!")

            # Check cooldown
            last_claim = parse(bp["last_claim"]) if bp["last_claim"] else None
            if last_claim and (datetime.utcnow() - last_claim).total_seconds() < 86400:
                next_claim = last_claim + timedelta(days=1)
                remaining = next_claim - datetime.utcnow()
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                return await ctx.send(
                    f"⏳ You can claim again in {hours}h {minutes}m!"
                )

            # Get reward for current day
            rewards = await self.config.rewards()
            current_day = bp["days_claimed"] + 1
            reward = rewards.get(str(current_day))

            if not reward:
                return await ctx.send("❌ Reward not configured for this day!")

            # Process reward
            currency_name = await self.get_currency_name(ctx)
            shop_cog = await self.get_shop_cog()

            if reward["type"] == "credits":
                amount = reward["amount"]
                await bank.deposit_credits(ctx.author, amount)
                message = f"💵 Received {amount} {currency_name}!"
            elif reward["type"] == "item":
                item_id = reward["id"]
                quantity = reward.get("quantity", 1)

                if not shop_cog:
                    return await ctx.send("❌ Shop system is not loaded!")

                await shop_cog.ensure_ready()

                # Check inventory space
                user_inv = await shop_cog.config.user(ctx.author).inventory()
                if len(user_inv) + quantity > 50:
                    return await ctx.send("❌ Your inventory is full! Free up space and try again.")

                # Add items
                for _ in range(quantity):
                    user_inv.append(item_id)

                await shop_cog.config.user(ctx.author).inventory.set(user_inv)
                item_name = shop_cog.shop_items[item_id]["name"]
                message = f"🎁 Received {quantity}x {item_name}!"
            else:
                return await ctx.send("❌ Invalid reward type configured!")

            # Update user data
            bp["last_claim"] = datetime.utcnow().isoformat()
            bp["days_claimed"] = current_day

        await ctx.send(
            f"🎉 Day {current_day} reward claimed! {message}\n"
            f"Total claimed: {current_day}/30 days"
        )

    @battlepass.command(name="status")
    async def battlepass_status(self, ctx):
        """Check your Battle Pass status"""
        bp = await self.config.user(ctx.author).battle_pass()

        if not bp["active"]:
            return await ctx.send("ℹ️ You don't have an active Battle Pass!")

        purchase_date = parse(bp["purchase_date"])
        days_active = (datetime.utcnow() - purchase_date).days
        days_left = 30 - days_active
        last_claim = parse(bp["last_claim"]) if bp["last_claim"] else None

        embed = discord.Embed(
            title="Battle Pass Status",
            color=discord.Color.gold()
        )
        embed.add_field(name="Purchased On", value=purchase_date.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="Days Active", value=f"{days_active}/30", inline=True)
        embed.add_field(name="Days Left", value=days_left, inline=True)
        embed.add_field(name="Rewards Claimed", value=f"{bp['days_claimed']}/30", inline=True)

        if last_claim:
            next_claim = last_claim + timedelta(days=1)
            if datetime.utcnow() < next_claim:
                remaining = next_claim - datetime.utcnow()
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                embed.add_field(name="Next Claim", value=f"{hours}h {minutes}m", inline=True)
            else:
                embed.add_field(name="Next Claim", value="Available Now!", inline=True)
        else:
            embed.add_field(name="Next Claim", value="Available Now!", inline=True)

        await ctx.send(embed=embed)

    @commands.group()
    @commands.admin()
    async def battlepassadmin(self, ctx):
        """Battle Pass admin commands"""
        pass

    @battlepassadmin.command(name="price")
    async def battlepass_price(self, ctx, price: int):
        """Set the Battle Pass price"""
        if price < 0:
            return await ctx.send("❌ Price must be positive!")

        await self.config.price.set(price)
        currency_name = await self.get_currency_name(ctx)
        await ctx.send(f"✅ Battle Pass price set to {price} {currency_name}!")

    @battlepassadmin.command(name="setreward")
    async def battlepass_setreward(self, ctx, day: int,
                                 reward_type: Literal["credits", "item"],
                                 *args):
        """Set a Battle Pass reward

        For credits: !battlepassadmin setreward [day] credits [amount]
        For items: !battlepassadmin setreward [day] item [item_id] [quantity=1]
        """
        if day < 1 or day > 30:
            return await ctx.send("❌ Day must be between 1-30!")

        rewards = await self.config.rewards()

        if reward_type == "credits":
            if len(args) != 1:
                return await ctx.send("❌ Usage: `!battlepassadmin setreward [day] credits [amount]`")

            try:
                amount = int(args[0])
            except ValueError:
                return await ctx.send("❌ Amount must be a number!")

            if amount <= 0:
                return await ctx.send("❌ Amount must be positive!")

            rewards[str(day)] = {"type": "credits", "amount": amount}

        elif reward_type == "item":
            if not args:
                return await ctx.send("❌ Usage: `!battlepassadmin setreward [day] item [item_id] [quantity=1]`")

            item_id = args[0].lower()
            quantity = int(args[1]) if len(args) > 1 else 1

            if quantity < 1:
                return await ctx.send("❌ Quantity must be at least 1!")

            # Verify item exists
            shop_cog = await self.get_shop_cog()
            if not shop_cog:
                return await ctx.send("❌ Shop system is not loaded!")

            await shop_cog.ensure_ready()
            if item_id not in shop_cog.shop_items:
                return await ctx.send("❌ Item does not exist in the shop!")

            rewards[str(day)] = {"type": "item", "id": item_id, "quantity": quantity}

        await self.config.rewards.set(rewards)
        await ctx.send(f"✅ Reward for day {day} set!")

    @battlepassadmin.command(name="viewrewards")
    async def battlepass_viewrewards(self, ctx):
        """View all Battle Pass rewards"""
        rewards = await self.config.rewards()
        shop_cog = await self.get_shop_cog()

        if shop_cog:
            await shop_cog.ensure_ready()

        if not rewards:
            return await ctx.send("ℹ️ No rewards configured yet!")

        embed = discord.Embed(
            title="Battle Pass Rewards",
            description="Configured rewards for each day",
            color=discord.Color.blue()
        )

        for day, reward in sorted(rewards.items(), key=lambda x: int(x[0])):
            if reward["type"] == "credits":
                embed.add_field(
                    name=f"Day {day}",
                    value=f"💰 {reward['amount']} credits",
                    inline=True
                )
            elif reward["type"] == "item" and shop_cog:
                item_data = shop_cog.shop_items.get(reward["id"], {})
                name = item_data.get("name", f"Unknown Item ({reward['id']})")
                embed.add_field(
                    name=f"Day {day}",
                    value=f"🎁 {reward.get('quantity', 1)}x {name}",
                    inline=True
                )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BattlePass(bot))
