import json
import asyncio
import discord
import math
from pathlib import Path
from uuid import uuid4
from typing import Literal, Optional
from redbot.core import commands, Config, bank, checks, data_manager
from discord.ui import Button, View

class PaginatorView(View):
    """View for paginating embeds with navigation buttons"""
    def __init__(self, embeds, timeout=60):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0
        self.message = None

        # Update button states
        self.update_buttons()

    def update_buttons(self):
        """Update button states based on current page"""
        # Clear existing buttons
        self.clear_items()

        # Previous button
        prev_button = Button(emoji="⬅️", style=discord.ButtonStyle.secondary,
                            disabled=self.current_page == 0)
        prev_button.callback = self.previous_page
        self.add_item(prev_button)

        # Page counter
        page_button = Button(label=f"{self.current_page+1}/{len(self.embeds)}",
                            style=discord.ButtonStyle.primary, disabled=True)
        self.add_item(page_button)

        # Next button
        next_button = Button(emoji="➡️", style=discord.ButtonStyle.secondary,
                            disabled=self.current_page == len(self.embeds)-1)
        next_button.callback = self.next_page
        self.add_item(next_button)

    async def previous_page(self, interaction):
        """Go to previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def next_page(self, interaction):
        """Go to next page"""
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def on_timeout(self):
        """Disable buttons when view times out"""
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class ShopSystem(commands.Cog):
    """Shop system with inventory, global shop, and player marketplace"""

    def __init__(self, bot):
        self.bot = bot
        self.data_path = data_manager.cog_data_path(self)
        self.shop_file = self.data_path / "shop_items.json"
        self.config = Config.get_conf(self, identifier=584930284)

        default_user = {
            "inventory": []
        }

        default_guild = {
            "market": []
        }

        self.config.register_user(**default_user)
        self.config.register_guild(**default_guild)

        # Initialize shop items
        self.shop_items = {}
        self.ready = asyncio.Event()
        bot.loop.create_task(self._load_shop_items())

    async def _load_shop_items(self):
        """Load shop items from JSON file"""
        try:
            # Create directory if it doesn't exist
            self.data_path.mkdir(parents=True, exist_ok=True)

            if not self.shop_file.exists():
                # Create default items if file doesn't exist
                default_items = {
                    "sword": {
                        "name": "Steel Sword",
                        "description": "A sharp blade for combat",
                        "price": 500,
                        "limited": True,
                        "quantity": 10,
                        "image_url": "https://raw.githubusercontent.com/yourusername/yourrepo/main/sword.png"
                    },
                    "potion": {
                        "name": "Health Potion",
                        "description": "Restores 50 HP",
                        "price": 100,
                        "limited": False,
                        "image_url": "https://raw.githubusercontent.com/yourusername/yourrepo/main/potion.png"
                    },
                    "shield": {
                        "name": "Wooden Shield",
                        "description": "Basic protection from attacks",
                        "price": 300,
                        "limited": True,
                        "quantity": 5,
                        "image_url": "https://raw.githubusercontent.com/yourusername/yourrepo/main/shield.png"
                    }
                }
                with self.shop_file.open("w") as f:
                    json.dump({"items": default_items}, f, indent=4)
                self.shop_items = default_items
            else:
                # Load existing items
                with self.shop_file.open("r") as f:
                    data = json.load(f)
                    self.shop_items = data.get("items", {})

                    # Ensure all items have required fields
                    for item_id, item_data in self.shop_items.items():
                        if "limited" not in item_data:
                            item_data["limited"] = False
                        if "quantity" not in item_data and item_data["limited"]:
                            item_data["quantity"] = 1
        except Exception as e:
            print(f"Error loading shop items: {e}")
            self.shop_items = {}
        finally:
            self.ready.set()

    async def _save_shop_items(self):
        """Save shop items to JSON file"""
        try:
            with self.shop_file.open("w") as f:
                json.dump({"items": self.shop_items}, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving shop items: {e}")
            return False

    async def ensure_ready(self):
        """Ensure shop data is loaded before proceeding"""
        await self.ready.wait()

    async def get_currency_name(self, ctx):
        """Get the currency name for the guild"""
        return await bank.get_currency_name(ctx.guild)

    @commands.command()
    async def shop(self, ctx):
        """View the global shop with pagination"""
        await self.ensure_ready()
        if not self.shop_items:
            return await ctx.send("🛒 The shop is currently empty!")

        currency_name = await self.get_currency_name(ctx)
        items_to_show = []

        # Collect available items
        for item_id, item_data in self.shop_items.items():
            if item_data.get("limited", False) and item_data.get("quantity", 0) <= 0:
                continue
            items_to_show.append((item_id, item_data))

        if not items_to_show:
            return await ctx.send("🛒 The shop is currently sold out! Check back later.")

        # Create paginated embeds
        embeds = []
        items_per_page = 5
        pages = (len(items_to_show) // items_per_page)
        if len(items_to_show) % items_per_page != 0:
            pages += 1

        for page in range(pages):
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_items = items_to_show[start_idx:end_idx]

            embed = discord.Embed(
                title=f"🛒 Global Shop - Page {page+1}/{pages}",
                color=discord.Color.blue()
            )

            for item_id, item_data in page_items:
                stock = "∞" if not item_data.get("limited", False) else f"{item_data['quantity']} left"
                embed.add_field(
                    name=f"{item_data['name']} ({item_id})",
                    value=f"💵 Price: {item_data['price']} {currency_name}\n"
                          f"📦 Stock: {stock}\n"
                          f"📝 {item_data['description']}",
                    inline=False
                )

            embed.set_footer(text=f"Use !buy [item_id] to purchase")
            embeds.append(embed)

        # Create and send paginator view
        view = PaginatorView(embeds)
        view.message = await ctx.send(embed=embeds[0], view=view)

    @commands.command()
    async def buy(self, ctx, item_id: str, quantity: int = 1):
        """Buy an item from the shop"""
        await self.ensure_ready()
        item_id = item_id.lower()
        item_data = self.shop_items.get(item_id)
        currency_name = await self.get_currency_name(ctx)

        if not item_data:
            return await ctx.send("❌ That item doesn't exist!")

        if quantity <= 0:
            return await ctx.send("❌ Quantity must be at least 1!")

        if item_data.get("limited", False):
            if item_data["quantity"] <= 0:
                return await ctx.send("❌ This item is out of stock!")
            if quantity > item_data["quantity"]:
                return await ctx.send(f"❌ Only {item_data['quantity']} available!")

        total_price = item_data["price"] * quantity
        user_balance = await bank.get_balance(ctx.author)

        if user_balance < total_price:
            return await ctx.send(f"❌ You need {total_price} {currency_name} to buy this!")

        # Check inventory space
        user_inv = await self.config.user(ctx.author).inventory()
        if len(user_inv) + quantity > 50:
            return await ctx.send("❌ Your inventory is full! (Max 50 items)")

        # Process transaction
        await bank.withdraw_credits(ctx.author, total_price)

        # Add items to inventory
        for _ in range(quantity):
            user_inv.append(item_id)

        await self.config.user(ctx.author).inventory.set(user_inv)

        # Update limited stock
        if item_data.get("limited", False):
            self.shop_items[item_id]["quantity"] -= quantity
            await self._save_shop_items()

        await ctx.send(f"✅ Purchased {quantity}x {item_data['name']} for {total_price} {currency_name}!")

    @commands.command()
    async def sell(self, ctx, item_id: str, quantity: int = 1):
        """Sell an item back to the shop for 80% of the original price"""
        await self.ensure_ready()
        item_id = item_id.lower()
        item_data = self.shop_items.get(item_id)
        currency_name = await self.get_currency_name(ctx)

        if not item_data:
            return await ctx.send("❌ That item doesn't exist in the shop!")

        if quantity <= 0:
            return await ctx.send("❌ Quantity must be at least 1!")

        # Get user inventory
        user_inv = await self.config.user(ctx.author).inventory()

        # Count how many of this item the user has
        item_count = user_inv.count(item_id)
        if item_count < quantity:
            return await ctx.send(f"❌ You only have {item_count} of this item!")

        # Calculate sell price (80% of original price, rounded down)
        sell_price_per_item = math.floor(item_data["price"] * 0.8)
        total_sell_price = sell_price_per_item * quantity

        # Remove items from inventory
        # We'll remove the specified quantity of this item
        removed = 0
        new_inv = [item for item in user_inv if not (item == item_id and (removed := removed + 1) <= quantity)]

        await self.config.user(ctx.author).inventory.set(new_inv)

        # Deposit money to user
        await bank.deposit_credits(ctx.author, total_sell_price)

        # Restock if it's a limited item
        if item_data.get("limited", False):
            self.shop_items[item_id]["quantity"] += quantity
            await self._save_shop_items()

        await ctx.send(f"✅ Sold {quantity}x {item_data['name']} for {total_sell_price} {currency_name}!")

    @commands.command()
    async def inventory(self, ctx, user: Optional[discord.User] = None):
        """View your inventory with pagination"""
        await self.ensure_ready()
        target = user or ctx.author
        user_inv = await self.config.user(target).inventory()

        if not user_inv:
            return await ctx.send(f"📭 {target.display_name}'s inventory is empty!")

        # Count items
        item_counts = {}
        for item_id in user_inv:
            item_counts[item_id] = item_counts.get(item_id, 0) + 1

        # Create paginated embeds
        embeds = []
        items_per_page = 9  # 3x3 grid
        items = list(item_counts.items())
        pages = (len(items) + items_per_page - 1) // items_per_page

        for page in range(pages):
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_items = items[start_idx:end_idx]

            embed = discord.Embed(
                title=f"🎒 {target.display_name}'s Inventory - Page {page+1}/{pages or 1}",
                description=f"{len(user_inv)}/50 slots used",
                color=discord.Color.green()
            )

            for item_id, count in page_items:
                item_data = self.shop_items.get(item_id, {"name": f"Unknown Item ({item_id})"})
                embed.add_field(
                    name=item_data["name"],
                    value=f"ID: `{item_id}`\nQuantity: {count}",
                    inline=True
                )

            # Add empty fields to keep grid alignment
            if len(page_items) % 3 != 0:
                for _ in range(3 - (len(page_items) % 3)):
                    embed.add_field(name="\u200b", value="\u200b", inline=True)

            embeds.append(embed)

        # Create and send paginator view
        view = PaginatorView(embeds)
        view.message = await ctx.send(embed=embeds[0], view=view)

    @commands.command()
    async def item(self, ctx, item_id: str):
        """View item information with image"""
        await self.ensure_ready()
        item_id = item_id.lower()
        item_data = self.shop_items.get(item_id)
        currency_name = await self.get_currency_name(ctx)

        if not item_data:
            return await ctx.send("❌ Item not found!")

        embed = discord.Embed(
            title=item_data["name"],
            description=item_data["description"],
            color=discord.Color.blue()
        )
        embed.add_field(name="Item ID", value=item_id, inline=True)
        embed.add_field(name="Price", value=f"{item_data['price']} {currency_name}", inline=True)

        # Calculate sell price (80% of original)
        sell_price = math.floor(item_data["price"] * 0.8)
        embed.add_field(name="Sell Price", value=f"{sell_price} {currency_name}", inline=True)

        if item_data.get("limited", False):
            stock = f"{item_data['quantity']} available"
        else:
            stock = "Unlimited supply"
        embed.add_field(name="Availability", value=stock, inline=False)

        # Add image if available
        if image_url := item_data.get("image_url"):
            embed.set_image(url=image_url)
        else:
            embed.add_field(name="Image", value="No image available", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def market(self, ctx):
        """View marketplace listings with pagination"""
        await self.ensure_ready()
        market_data = await self.config.guild(ctx.guild).market()
        currency_name = await self.get_currency_name(ctx)

        if not market_data:
            return await ctx.send("ℹ️ The marketplace is empty!")

        # Create paginated embeds
        embeds = []
        items_per_page = 5
        pages = (len(market_data) + items_per_page - 1) // items_per_page

        for page in range(pages):
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_listings = market_data[start_idx:end_idx]

            embed = discord.Embed(
                title=f"🏪 Player Marketplace - Page {page+1}/{pages or 1}",
                color=discord.Color.orange()
            )

            for listing in page_listings:
                seller = self.bot.get_user(listing["seller_id"])
                item_data = self.shop_items.get(listing["item_id"], {"name": f"Unknown Item ({listing['item_id']})"})

                embed.add_field(
                    name=f"{item_data['name']} - 💵 {listing['price']} {currency_name}",
                    value=f"Seller: {seller.mention if seller else 'Unknown'}\n"
                          f"Listing ID: `{listing['id']}`\n"
                          f"Item ID: `{listing['item_id']}`",
                    inline=False
                )

            embed.set_footer(text=f"Use !buymarket [listing_id] to purchase")
            embeds.append(embed)

        # Create and send paginator view
        view = PaginatorView(embeds)
        view.message = await ctx.send(embed=embeds[0], view=view)

    @commands.command()
    async def buymarket(self, ctx, listing_id: str):
        """Buy an item from the marketplace

        Example: !buymarket d93a8b7c-...
        """
        await self.ensure_ready()
        market_data = await self.config.guild(ctx.guild).market()
        currency_name = await self.get_currency_name(ctx)

        listing = next((l for l in market_data if l["id"] == listing_id), None)

        if not listing:
            return await ctx.send("❌ Listing not found!")

        # Check buyer's balance
        buyer_balance = await bank.get_balance(ctx.author)
        if buyer_balance < listing["price"]:
            return await ctx.send(f"❌ You need {listing['price']} {currency_name} to buy this!")

        # Check inventory space
        buyer_inv = await self.config.user(ctx.author).inventory()
        if len(buyer_inv) >= 50:
            return await ctx.send("❌ Your inventory is full! (Max 50 items)")

        # Process transaction
        seller = ctx.guild.get_member(listing["seller_id"])
        if seller:
            await bank.deposit_credits(seller, listing["price"])
        await bank.withdraw_credits(ctx.author, listing["price"])

        # Transfer item
        buyer_inv.append(listing["item_id"])
        await self.config.user(ctx.author).inventory.set(buyer_inv)

        # Remove listing
        market_data = [l for l in market_data if l["id"] != listing_id]
        await self.config.guild(ctx.guild).market.set(market_data)

        await ctx.send(f"✅ Purchased item from marketplace for {listing['price']} {currency_name}!")

    @commands.command()
    async def sellmarket(self, ctx, item_id: str, price: int):
        """Sell an item on the marketplace

        Example: !sellmarket sword 500
        """
        await self.ensure_ready()
        currency_name = await self.get_currency_name(ctx)

        if price <= 0:
            return await ctx.send("❌ Price must be positive!")

        item_id = item_id.lower()
        user_inv = await self.config.user(ctx.author).inventory()

        # Check if item exists in inventory
        if item_id not in user_inv:
            return await ctx.send("❌ You don't have that item in your inventory!")

        # Check if item exists in shop
        if item_id not in self.shop_items:
            return await ctx.send("❌ That item doesn't exist in the shop!")

        # Remove item from inventory
        user_inv.remove(item_id)
        await self.config.user(ctx.author).inventory.set(user_inv)

        # Create listing
        new_listing = {
            "id": str(uuid4()),
            "seller_id": ctx.author.id,
            "item_id": item_id,
            "price": price
        }

        market_data = await self.config.guild(ctx.guild).market()
        market_data.append(new_listing)
        await self.config.guild(ctx.guild).market.set(market_data)

        await ctx.send(f"✅ Listed {self.shop_items[item_id]['name']} for {price} {currency_name}!")

    # Admin commands
    @checks.admin()
    @commands.command()
    async def shopfile(self, ctx):
        """Display the path to the shop items JSON file (Admin only)"""
        # Get absolute path to the JSON file
        abs_path = self.shop_file.resolve()

        # Check if file exists
        file_exists = self.shop_file.exists()

        # Create embed with information
        embed = discord.Embed(
            title="Shop System File Path",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="JSON File Path",
            value=f"`{abs_path}`",
            inline=False
        )
        embed.add_field(
            name="File Exists",
            value="✅ Yes" if file_exists else "❌ No",
            inline=False
        )
        embed.add_field(
            name="File Size",
            value=f"{abs_path.stat().st_size} bytes" if file_exists else "N/A",
            inline=False
        )

        # Add troubleshooting tips
        if not file_exists:
            embed.add_field(
                name="Troubleshooting",
                value="The file doesn't exist. The cog should create it automatically when loaded for the first time.",
                inline=False
            )

        await ctx.send(embed=embed)

        # If file exists, offer to show contents
        if file_exists:
            await ctx.send("Would you like to see the file contents? Type `yes` to confirm.")
            try:
                response = await self.bot.wait_for(
                    "message",
                    timeout=30,
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                )
                if response.content.lower() == "yes":
                    with open(self.shop_file, 'r') as f:
                        content = f.read()
                        # Discord has 2000 char limit, so truncate if needed
                        if len(content) > 1900:
                            content = content[:1900] + "\n... (truncated)"
                        await ctx.send(f"```json\n{content}\n```")
            except asyncio.TimeoutError:
                pass

    @checks.admin()
    @commands.command()
    async def shopadd(self, ctx, item_id: str, name: str, price: int,
                     description: str, image_url: str,
                     limited: Literal["yes", "no"] = "no", quantity: int = 1):
        """Add a new item to the shop (Admin only)

        Example: !shopadd gem "Rare Gem" 1000 "Shiny gem" https://.../gem.png yes 5
        """
        await self.ensure_ready()
        item_id = item_id.lower()
        if item_id in self.shop_items:
            return await ctx.send("❌ Item ID already exists!")

        self.shop_items[item_id] = {
            "name": name,
            "price": price,
            "description": description,
            "image_url": image_url,
            "limited": (limited.lower() == "yes")
        }

        if self.shop_items[item_id]["limited"]:
            self.shop_items[item_id]["quantity"] = quantity

        if await self._save_shop_items():
            await ctx.send(f"✅ Added {name} to the shop!")
        else:
            await ctx.send("❌ Failed to save shop items!")

    @checks.admin()
    @commands.command()
    async def shopimage(self, ctx, item_id: str, image_url: str):
        """Edit an item's image URL (Admin only)

        Example: !shopimage sword https://.../new_sword.png
        """
        await self.ensure_ready()
        item_id = item_id.lower()
        if item_id not in self.shop_items:
            return await ctx.send("❌ Item not found!")

        self.shop_items[item_id]["image_url"] = image_url
        if await self._save_shop_items():
            await ctx.send(f"✅ Updated image for {self.shop_items[item_id]['name']}!")
        else:
            await ctx.send("❌ Failed to save shop items!")

    @checks.admin()
    @commands.command()
    async def shoprestock(self, ctx, item_id: str, quantity: int):
        """Restock a limited item (Admin only)

        Example: !shoprestock sword 10
        """
        await self.ensure_ready()
        item_id = item_id.lower()
        if item_id not in self.shop_items:
            return await ctx.send("❌ Item not found!")

        if not self.shop_items[item_id].get("limited", False):
            return await ctx.send("❌ This item is not limited!")

        self.shop_items[item_id]["quantity"] += quantity
        if await self._save_shop_items():
            await ctx.send(f"✅ Restocked {self.shop_items[item_id]['name']} by {quantity} units!")
        else:
            await ctx.send("❌ Failed to save shop items!")

async def setup(bot):
    await bot.add_cog(ShopSystem(bot))
