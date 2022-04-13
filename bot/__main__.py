#!/usr/bin/env python3

import bot
import discord
import os

from .reactions import setup_reaction_listeners
from .app_commands import setup_app_commands
#from .slash_commands import SlashCommands

client = discord.Client(
    command_prefix="!",
    help_command=None,
    intents=discord.Intents(guilds=True, guild_reactions=True, members=True, messages=True),
)


@client.event
async def on_ready():
    print("Ready")


try:
    token = os.environ["DISCORD_TOKEN"]
except KeyError:
    raise SystemExit("You need to specify the environment variable DISCORD_TOKEN before running the bot!")

setup_app_commands(client)
setup_reaction_listeners(client)
# client.add_cog(SlashCommands())

client.run(token)
