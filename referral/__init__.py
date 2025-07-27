from .referral import ReferralSystem


async def setup(bot):
    await bot.add_cog(ReferralSystem(bot))
