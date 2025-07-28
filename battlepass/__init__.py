from .battlepass import BattlePass


async def setup(bot):
    await bot.add_cog(BattlePass(bot))
