from redbot.core import commands, Config, bank
from redbot.core.errors import BalanceTooHigh, BankError
import discord
from discord.ui import Button, View
import random

class CombatGame(commands.Cog):
    """JRPG-style Combat System with Healing"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=246813579)
        self.config.register_user(
            health=100,
            max_health=100,
            attack=15,
            defense=5
        )
        self.active_combats = {}
        self.reward_amount = 50  # Credits per victory
        self.heal_cost = 100  # Cost to fully heal

    @commands.command()
    @commands.is_owner()
    async def resetplayer(self, ctx, user: discord.User):
        await self.config.user(user).clear()
        await ctx.send(f"Reset {user.name}'s data!")

    @commands.command()
    async def heal(self, ctx):
        """Restore your health to full for 100 credits"""
        user = ctx.author

        # Ensure user is initialized
        await self.initialize_user(user)

        # Check if user is in combat
        if user.id in self.active_combats:
            return await ctx.send("You can't heal while in combat!")

        # Get player stats
        health = await self.config.user(user).health()
        max_health = await self.config.user(user).max_health()

        # Check if already at full health
        if health >= max_health:
            return await ctx.send("You're already at full health!")

        # Check player's balance
        try:
            balance = await bank.get_balance(user)
            if balance < self.heal_cost:
                currency_name = await bank.get_currency_name(ctx.guild)
                return await ctx.send(
                    f"You need {self.heal_cost} {currency_name} to heal! "
                    f"You only have {balance} {currency_name}."
                )

            # Deduct credits
            await bank.withdraw_credits(user, self.heal_cost)

            # Restore health
            await self.config.user(user).health.set(max_health)

            # Get currency name for display
            currency_name = await bank.get_currency_name(ctx.guild)

            # Create success embed
            embed = discord.Embed(
                title="💖 Healing Complete!",
                description=(
                    f"Your health has been restored to {max_health}!\n"
                    f"Paid {self.heal_cost} {currency_name}\n"
                    f"New balance: {balance - self.heal_cost} {currency_name}"
                ),
                color=0x00ff00
            )
            await ctx.send(embed=embed)

        except BankError as e:
            await ctx.send(f"Healing failed: {str(e)}")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    async def initialize_user(self, user):
        """Ensure user has initial stats"""
        async with self.config.user(user).all() as user_data:
            if user_data["health"] == 0:  # If new user
                user_data["health"] = 100
                user_data["max_health"] = 100
                user_data["attack"] = 15
                user_data["defense"] = 5

    @commands.command()
    async def combat(self, ctx):
        """Start a combat encounter"""
        user = ctx.author
        user_id = user.id

        # Ensure user is initialized
        await self.initialize_user(user)

        # Check if user already in combat
        if user_id in self.active_combats:
            return await ctx.send("You're already in combat!")

        # Get player health from config
        player_health = await self.config.user(user).health()

        # Initialize combat
        combat_data = {
            "player_health": player_health,
            "enemy_health": random.randint(40, 150),
            "player_defending": False,
            "enemy_defending": False,
            "message": None
        }
        self.active_combats[user_id] = combat_data

        # Create combat interface
        embed = await self.create_combat_embed(user, combat_data)
        view = self.create_combat_view()
        combat_data["message"] = await ctx.send(embed=embed, view=view)

    async def create_combat_embed(self, user, combat_data):
        """Create embed for combat"""
        max_health = await self.config.user(user).max_health()

        embed = discord.Embed(
            title=f"⚔️ {user.display_name}'s Battle",
            color=0xff0000
        )
        embed.add_field(
            name="Your Health",
            value=f"❤️ {combat_data['player_health']}/{max_health}",
            inline=True
        )

        # Show enemy status with defense icon if defending
        enemy_status = "💀"
        if combat_data["enemy_defending"]:
            enemy_status = "🛡️"
        embed.add_field(
            name="Enemy Health",
            value=f"{enemy_status} {combat_data['enemy_health']}",
            inline=True
        )

        # Show reward info if available
        if await bank.is_global():
            currency_name = await bank.get_currency_name(ctx.guild)
            embed.set_footer(text=f"Reward: {self.reward_amount} {currency_name} per victory")
        return embed

    def create_combat_view(self):
        """Create button view"""
        view = View(timeout=60.0)

        # Attack Button
        attack_btn = Button(style=discord.ButtonStyle.danger, label="⚔️ Attack")
        attack_btn.callback = self.attack_handler
        view.add_item(attack_btn)

        # Defend Button
        defend_btn = Button(style=discord.ButtonStyle.primary, label="🛡️ Defend")
        defend_btn.callback = self.defend_handler
        view.add_item(defend_btn)

        return view

    async def enemy_turn(self, user, combat_data):
        """Enemy AI: Randomly choose to attack or defend"""
        # 70% chance to attack, 30% chance to defend
        if random.random() < 0.7:
            # Enemy attacks
            enemy_damage = random.randint(8, 12)

            # Reduce damage if player is defending
            if combat_data["player_defending"]:
                enemy_damage = max(1, enemy_damage // 2)  # At least 1 damage
                combat_data["player_defending"] = False  # Reset defense
                return f"The enemy attacks! You block for **{enemy_damage}** reduced damage!"
            else:
                combat_data["player_health"] = max(0, combat_data["player_health"] - enemy_damage)
                return f"The enemy attacks for **{enemy_damage}** damage!"
        else:
            # Enemy defends
            combat_data["enemy_defending"] = True
            return "The enemy assumes a defensive stance! 🛡️"

    async def award_victory_rewards(self, user, embed):
        """Award credits to user after victory"""
        try:
            # Get currency name based on bank configuration
            if await bank.is_global():
                currency_name = await bank.get_currency_name(None)
            else:
                currency_name = await bank.get_currency_name(user.guild)

            # Deposit credits
            await bank.deposit_credits(user, self.reward_amount)

            # Add reward message to embed
            embed.description += f"\n\n🏆 **Victory Reward**: {self.reward_amount} {currency_name}!"

            # Check new balance
            new_balance = await bank.get_balance(user)
            embed.set_footer(text=f"New balance: {new_balance} {currency_name}")

        except BalanceTooHigh:
            max_balance = await bank.get_max_balance(user)
            await bank.set_balance(user, max_balance)
            currency_name = await bank.get_currency_name(user.guild)
            embed.description += f"\n\n🏆 **Victory Reward**: Reached max {currency_name} capacity!"
        except Exception as e:
            embed.description += f"\n\n⚠️ Reward failed: {str(e)}"

    async def attack_handler(self, interaction):
        user = interaction.user
        user_id = user.id

        if user_id not in self.active_combats:
            await interaction.response.send_message("No active combat!", ephemeral=True)
            return

        combat_data = self.active_combats[user_id]

        # Player attack
        player_attack = await self.config.user(user).attack()
        base_damage = random.randint(player_attack - 5, player_attack + 5)

        # Reduce damage if enemy is defending
        if combat_data["enemy_defending"]:
            damage = max(1, base_damage // 2)  # At least 1 damage
            combat_data["enemy_defending"] = False  # Reset defense
            damage_msg = f"You attack for **{damage}** reduced damage! (Enemy defended)"
        else:
            damage = base_damage
            damage_msg = f"You attack for **{damage}** damage!"

        combat_data["enemy_health"] = max(0, combat_data["enemy_health"] - damage)
        combat_data["player_defending"] = False  # Player wasn't defending this turn

        # Enemy turn if still alive
        enemy_msg = ""
        if combat_data["enemy_health"] > 0:
            enemy_msg = await self.enemy_turn(user, combat_data)

        # Update embed
        embed = await self.create_combat_embed(user, combat_data)
        embed.description = f"{damage_msg}\n{enemy_msg}"

        # Check combat outcome
        if combat_data["player_health"] <= 0:
            embed.description += "\n\n**You were defeated!**"
            await interaction.response.edit_message(embed=embed, view=None)
            del self.active_combats[user_id]
            return

        if combat_data["enemy_health"] <= 0:
            embed.description += "\n\n**You defeated the enemy!**"
            await self.config.user(user).health.set(combat_data["player_health"])

            # Award victory rewards
            await self.award_victory_rewards(user, embed)

            await interaction.response.edit_message(embed=embed, view=None)
            del self.active_combats[user_id]
            return

        await interaction.response.edit_message(embed=embed)

    async def defend_handler(self, interaction):
        user = interaction.user
        user_id = user.id

        if user_id not in self.active_combats:
            await interaction.response.send_message("No active combat!", ephemeral=True)
            return

        combat_data = self.active_combats[user_id]
        combat_data["player_defending"] = True
        combat_data["enemy_defending"] = False  # Reset enemy defense

        # Enemy turn
        enemy_msg = await self.enemy_turn(user, combat_data)

        # Update embed
        embed = await self.create_combat_embed(user, combat_data)
        embed.description = f"You assume a defensive stance! 🛡️\n{enemy_msg}"

        # Check combat outcome
        if combat_data["player_health"] <= 0:
            embed.description += "\n\n**You were defeated!**"
            await interaction.response.edit_message(embed=embed, view=None)
            del self.active_combats[user_id]
            return

        await interaction.response.edit_message(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def setreward(self, ctx, amount: int):
        """Set the victory reward amount (owner only)"""
        if amount < 0:
            return await ctx.send("Reward amount must be positive!")

        self.reward_amount = amount
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"Victory reward set to {amount} {currency_name}!")


    @commands.command()
    @commands.is_owner()
    async def sethealcost(self, ctx, cost: int):
        """Set the healing cost amount (owner only)"""
        if cost < 1:
            return await ctx.send("Healing cost must be at least 1 credit!")

        self.heal_cost = cost
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"Healing cost set to {cost} {currency_name}!")

    @commands.Cog.listener()
    async def on_view_timeout(self, view):
        """Clean up timed out combats"""
        for user_id, data in list(self.active_combats.items()):
            if data["message"] and data["message"].id == view.message.id:
                del self.active_combats[user_id]

async def setup(bot):
    await bot.add_cog(CombatGame(bot))
