#!/usr/bin/env python3

import bot
import discord
import os
from discord.ext import commands

from .reactions import listen_for_reactions
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
listen_for_reactions(client)
# client.add_cog(SlashCommands())
client.run(token)
