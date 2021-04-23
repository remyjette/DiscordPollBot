import asyncio
import discord
import sys
from discord.ext import commands

import bot
from .emoji import allowed_emoji
from .poll import Poll, PollException


class Reactions(commands.Cog):
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await bot.instance.wait_until_ready()

        if payload.user_id == bot.instance.user.id:
            return
        channel = bot.instance.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != bot.instance.user:
            return

        for reaction in message.reactions:
            if not reaction.me:
                await message.clear_reaction(reaction.emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await bot.instance.wait_until_ready()

        channel = bot.instance.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != bot.instance.user:
            return
        emoji = payload.emoji.name
        reaction = discord.utils.find(lambda r: r.emoji == emoji, message.reactions)

        if not message.embeds:
            return

        elif payload.user_id == bot.instance.user.id:
            # Someone with the 'Manage Messages' permissions removed our reaction. Add our reaction back, they should
            # use /removeoption instead.
            await message.add_reaction(emoji)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload):
        await bot.instance.wait_until_ready()

        channel = bot.instance.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != bot.instance.user:
            return
        elif not message.embeds:
            return

        # Someone with the 'Manage Messages' permissions used 'Remove All Reactions' on our poll. The existing votes
        # were lost, but we can at least re-populate the poll.

        current_emoji = [line[0] for line in message.embeds[0].description.split("\n") if line[0] in allowed_emoji]
        await asyncio.gather(*[message.add_reaction(emoji) for emoji in current_emoji])
