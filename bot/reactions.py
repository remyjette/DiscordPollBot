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

        elif reaction and payload.user_id == bot.instance.user.id:
            # Someone used 'Manage Messages' to clear our reaction when someone has an existing vote for this option!
            # Add our reaction back, they should use !removeoption instead.
            await message.add_reaction(emoji)

        elif reaction and reaction.count == 1 and reaction.me:
            # Someone else removed the last vote, so clear it. This will also trigger on_raw_reaction_clear_emoji
            # below to remove the poll option from the message text.
            await reaction.clear()

        elif not reaction:
            # The reaction is completely gone (someone deleted the bot emoji) and this option had no votes. Treat it
            # as if reaction.clear() were called which will remove the poll option from the message text.
            await self.on_raw_reaction_clear_emoji(payload)

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload):
        await bot.instance.wait_until_ready()

        emoji = payload.emoji.name
        if emoji not in allowed_emoji:
            return

        channel = bot.instance.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != bot.instance.user:
            return
        if not message.embeds:
            return

        poll = Poll(message, current_user=None)
        try:
            await poll.remove_option(emoji=emoji)
        except PollException:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload):
        await bot.instance.wait_until_ready()

        channel = bot.instance.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != bot.instance.user:
            return
        elif not message.embeds:
            return

        current_emoji = [line[0] for line in message.embeds[0].description.split("\n") if line[0] in allowed_emoji]
        await asyncio.gather(*[message.add_reaction(emoji) for emoji in current_emoji])
