import asyncio
import discord
import sys
from discord.ext import commands
from poll_options import remove_poll_option


class Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.bot.wait_until_ready()

        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            return

        for reaction in message.reactions:
            if not reaction.me:
                await message.clear_reaction(reaction.emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.bot.wait_until_ready()

        if payload.user_id == self.bot.user.id:
            return
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != self.bot.user:
            return
        emoji = payload.emoji.name
        reaction = discord.utils.find(lambda r: r.emoji == emoji, message.reactions)
        if reaction is None:
            return
        if reaction.count != 1 or not reaction.me:
            return
        assert len(message.embeds) == 1

        embed = message.embeds[0]
        remove_poll_option(embed, emoji)
        await asyncio.gather(message.edit(embed=embed), reaction.clear())
