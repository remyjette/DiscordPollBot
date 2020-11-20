#!/usr/bin/env python3

import discord
import os
import sys
from discord.ext import commands

from commands import Commands, DiscordBotHelpCommand
from reactions import Reactions

# TODOS:
# 1) what if I want a comma in a vote option?

bot = commands.Bot(
    command_prefix="!",
    help_command=DiscordBotHelpCommand(),
    intents=discord.Intents(guilds=True, guild_reactions=True, messages=True),
)

@bot.event
async def on_ready():
    print("Ready")


if __name__ == "__main__":
    try:
        token = os.environ["DISCORD_TOKEN"]
    except KeyError:
        print("You need to specify the environment variable DISCORD_TOKEN before running the bot!", file=sys.stderr)
        sys.exit(1)
    bot.add_cog(Commands(bot))
    bot.add_cog(Reactions(bot))
    bot.run(token)
