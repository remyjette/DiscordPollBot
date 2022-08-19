#!/usr/bin/env python3

import os

import discord

import bot
from .app_commands import setup_app_commands
from .reactions import setup_reaction_listeners

client = discord.Client(
    help_command=None,
    intents=discord.Intents(
        guilds=True,  # Finding the message from raw event in reactions.py, removing channel/role mentions in utils.py
        guild_reactions=True,  # Keeping poll reactions in a valid state in reactions.py
        members=False,  # Removing user mentions in utils.py
        messages=True,  # Be able to respond to DMs with our OAuth URL, be able to cache Message objects
    ),
)

try:
    token = os.environ["DISCORD_TOKEN"]
except KeyError:
    raise SystemExit("You need to specify the environment variable DISCORD_TOKEN before running the bot!")

setup_app_commands(client)
setup_reaction_listeners(client)


@client.event
async def on_message(message: discord.Message):
    if message.channel.type == discord.ChannelType.private and message.author != client.user:
        await message.reply(
            "Polls in direct messges aren't supported, but you can add me to your server at "
            + discord.utils.oauth_url(
                client_id=client.user.id,
                permissions=bot.required_permissions,
            )
        )


client.run(token, root_logger=True)
