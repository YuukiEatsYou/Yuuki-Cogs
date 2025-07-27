from .shop import ShopSystem


async def setup(bot):
    await bot.add_cog(ShopSystem(bot))
