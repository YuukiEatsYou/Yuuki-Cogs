from .tutorial import TutorialCog


async def setup(bot):
    await bot.add_cog(TutorialCog(bot))
