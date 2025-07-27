from .combat import CombatGame


async def setup(bot):
    await bot.add_cog(CombatGame(bot))
