from .reactionmonitor import ReactionMonitor


async def setup(bot):
    await bot.add_cog(ReactionMonitor(bot))
