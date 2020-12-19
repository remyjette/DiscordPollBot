#!/usr/bin/env python3

import bot
import discord
import os
from discord.ext import commands

from .commands import Commands, DiscordBotHelpCommand
from .reactions import Reactions
from .slash_commands import SlashCommands

bot.instance = commands.Bot(
    command_prefix="!",
    help_command=DiscordBotHelpCommand(),
    intents=discord.Intents(guilds=True, guild_reactions=True, messages=True),
)


@bot.instance.event
async def on_ready():
    print("Ready")


try:
    token = os.environ["DISCORD_TOKEN"]
except KeyError:
    raise SystemExit("You need to specify the environment variable DISCORD_TOKEN before running the bot!")
bot.instance.add_cog(Commands())
bot.instance.add_cog(Reactions())
bot.instance.add_cog(SlashCommands())
bot.instance.run(token)
