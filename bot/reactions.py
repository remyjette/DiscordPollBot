import asyncio
import discord

from .emoji import allowed_emoji


def setup_reaction_listeners(client: discord.Client):
    @client.event
    async def on_raw_reaction_add(payload):
        await client.wait_until_ready()

        if payload.user_id == client.user.id:
            return
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != client.user:
            return

        for reaction in message.reactions:
            if not reaction.me:
                await message.clear_reaction(reaction.emoji)

    @client.event
    async def on_raw_reaction_remove(payload):
        await client.wait_until_ready()

        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != client.user:
            return
        emoji = payload.emoji.name
        reaction = discord.utils.find(lambda r: r.emoji == emoji, message.reactions)

        if not message.embeds:
            return

        elif payload.user_id == client.user.id:
            # Someone with the 'Manage Messages' permissions removed our reaction. Add our reaction back, they should
            # use /removeoption instead.
            await message.add_reaction(emoji)

    @client.event
    async def on_raw_reaction_clear(payload):
        await client.wait_until_ready()

        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author != client.user:
            return
        elif not message.embeds:
            return

        # Someone with the 'Manage Messages' permissions used 'Remove All Reactions' on our poll. The existing votes
        # were lost, but we can at least re-populate the poll.

        current_emoji = [line[0] for line in message.embeds[0].description.split("\n") if line[0] in allowed_emoji]
        await asyncio.gather(*[message.add_reaction(emoji) for emoji in current_emoji])
