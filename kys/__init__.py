from .kys import KysCog


async def setup(bot):
    await bot.add_cog(KysCog(bot))
