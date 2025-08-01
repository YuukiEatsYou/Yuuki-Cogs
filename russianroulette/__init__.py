from .rr import RussianRoulette


async def setup(bot):
    await bot.add_cog(RussianRoulette(bot))
