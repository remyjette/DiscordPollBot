#!/usr/bin/env python3

import asyncio
import discord
import os
import string
import sys
from discord.ext import commands
from shlex import shlex

from utils import EMOJI_A, EMOJI_Z, NUMBER_TO_EMOJI_UNICODE, number_to_emoji, emoji_to_number

required_permissions = discord.Permissions(
    read_messages=True,  # To see commands sent by users
    send_messages=True,  # To send the poll message
    manage_messages=True,  # To clear invalid reacts from users
    embed_links=True,  # To embed the poll as a rich content card
    read_message_history=True,  # To find the poll when a user does !addoption or !removeoption
    add_reactions=True,  # To add the initial reactions for users to be able to click on to vote
)

# TODOS:
# 1) what if I want a comma in a vote option?
# 2) Complain if we don't have permissions

# In arg_types, 'list' is a list of strings
arg_types = {"title": str, "options": list, "new_options_allowed": bool}



class MyHelpCommand(commands.MinimalHelpCommand):
    def get_ending_note(self):
        return (
            "Like this bot? Add it to your own servers by clicking "
            f"<https://discord.com/oauth2/authorize?client_id={bot.user.id}"
            f"&scope=bot&permissions={required_permissions.value}>"
        )

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page, delete_after=30)


bot = commands.Bot(
    command_prefix="!",
    help_command=MyHelpCommand(),
    intents=discord.Intents(guilds=True, guild_reactions=True, messages=True),
)


def is_admin():
    def predicate(ctx):
        return ctx.guild is not None and ctx.author.guild_permissions.administrator

    return commands.check(predicate)


@bot.command()
@commands.check_any(commands.is_owner(), is_admin())
async def removeallpolls(ctx):
    await ctx.channel.purge(check=(lambda m: m.author == ctx.me))


def parse_command_args(text):
    lexer = shlex(text, posix=True)
    lexer.whitespace = " "
    lexer.wordchars += string.punctuation
    return dict(word.split("=", maxsplit=1) for word in lexer)


def add_poll_option(embed, option):
    if embed.description == discord.Embed.Empty:
        new_option_emoji = number_to_emoji(1)
        embed.description = new_option_emoji + " " + option
        return new_option_emoji

    description_lines = embed.description.split("\n")

    if len(description_lines) >= 20:
        # Discord has a limit of 20 reactions per message. If we're already at 20, one will need to be removed first.
        return None

    # Make sure we don't already have this option
    for line in description_lines:
        last_seen_emoji, last_seen_option = line.split(" ", maxsplit=1)
        if option == last_seen_option:
            return None

    if last_seen_emoji == EMOJI_Z:
        # We have no more letters to use, so no more options can be added to this poll even if options are removed.
        return None

    new_option_emoji = number_to_emoji(emoji_to_number(last_seen_emoji) + 1)
    assert new_option_emoji is not None

    description_lines.append(new_option_emoji + " " + option)

    embed.description = "\n".join(description_lines)
    return new_option_emoji


def remove_poll_option(embed, option=None, emoji=None):
    assert option or emoji

    if not emoji:
        if emoji_to_number(option) is not None:
            emoji = option
            option = None
        elif len(option) == 1 and option.isdigit():
            emoji = option + NUMBER_TO_EMOJI_UNICODE
            option = None
        elif len(option) == 1 and ord("A") <= (option_ord := ord(option.upper())) <= ord("Z"):
            emoji = chr(ord(EMOJI_A) + option_ord - ord("A"))
            option = None

    def filtered_lines(lines):
        nonlocal emoji
        iterator = iter(lines)
        for line in iterator:
            if emoji and line.startswith(emoji):
                break
            if option is not None:
                line_emoji, line_option = line.split(" ", maxsplit=1)
                if line_option == option:
                    emoji = line_emoji
                    break
            yield line
        yield from iterator

    # Copy the string before we start changing it, so we can return an error if we did nothing
    before = embed.description
    embed.description = "\n".join(filtered_lines(embed.description.split("\n")))

    if embed.description == before:
        return None

    return emoji


@bot.event
async def on_raw_reaction_add(payload):
    await bot.wait_until_ready()

    if payload.user_id == bot.user.id:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if message.author != bot.user:
        return

    for reaction in message.reactions:
        if not reaction.me:
            await message.clear_reaction(reaction.emoji)


@bot.event
async def on_raw_reaction_remove(payload):
    await bot.wait_until_ready()

    if payload.user_id == bot.user.id:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if message.author != bot.user:
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


@bot.after_invoke
async def cleanup_command(ctx):
    await ctx.message.delete()


@bot.command(
    brief="Create a new poll",
    help="Creates a new poll",
    usage="<title> or !startpoll title=Title, options=option1,option2",
)
async def startpoll(ctx, *, args):
    settings = {}
    if "title=" not in args and any(f"{arg_name}=" in args for arg_name in arg_types):
        await ctx.send(
            f"{ctx.author.mention} When specifying multiple arguments the title argument is required.", delete_after=10
        )
        return

    if "title=" in args:
        for name, value in parse_command_args(args).items():
            if name not in arg_types:
                await ctx.send(f"{ctx.author.mention} Did not understand the argument '{name}'", delete_after=10)
                return
            if arg_types[name] == list:
                settings[name] = value.split(",")
            elif arg_types[name] == bool:
                settings[name] = discord.ext.commands.core._convert_to_bool(value)
            elif arg_types[name] == str:
                settings[name] = arg_types[name](value)
            else:
                raise RuntimeError(f"Don't understand type '{arg_types[name].__name__}' for arg '{name}'")
    else:
        settings["title"] = args

    embed = discord.Embed()
    if "title" in settings:
        embed.title = settings["title"]
    embed.add_field(name="Poll created by", value=ctx.author.mention, inline=True)
    embed.add_field(name="Adding options allowed", value=":white_check_mark:", inline=True)

    initial_emojis = []
    if "options" in settings:
        for option in settings["options"]:
            if option:
                if emoji := add_poll_option(embed, option):
                    initial_emojis.append(emoji)

    message = await ctx.send(embed=embed)
    if initial_emojis:
        await asyncio.gather(*(message.add_reaction(emoji) for emoji in initial_emojis))


@startpoll.error
async def startpoll_error(ctx, error):
    await ctx.message.delete()
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} You forgot to provide the poll title!", delete_after=10)


def get_last_poll_message(ctx):
    return ctx.history().find(lambda m: m.author == ctx.me and len(m.embeds) > 0)


@bot.command(
    brief="Add an option to an existing poll",
    help=f"Adds a new option to an existing poll.\n\nThere must be fewer than 20 existing options, and {EMOJI_Z} must not already be in use.\n\nExample: !addoption Pizza Bagels",
    usage="<new option>",
)
async def addoption(ctx, *, arg):
    last_poll_message = await get_last_poll_message(ctx)
    if last_poll_message is None:
        await ctx.send(
            f"{ctx.author.mention} Couldn't find a poll to add an option to. Did you forget to !startpoll first?",
            delete_after=10,
        )
        return
    embed = last_poll_message.embeds[0]
    if emoji := add_poll_option(embed, arg):
        await asyncio.gather(last_poll_message.edit(embed=embed), last_poll_message.add_reaction(emoji))
    else:
        await ctx.send(f"{ctx.author.mention} Couldn't add option '{arg}'", delete_after=10)

@addoption.error
async def addoption_error(ctx, error):
    await ctx.message.delete()
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} You have to provide the new option when using !addoption", delete_after=10)


@bot.command(
    brief="Remove an option from an existing poll",
    help=f"Removes an option to an existing poll.\n\nYou can specify either the letter/number for the option, use the emoji, or just name the text of the option.\n\nExamples:\n!removeoption 3\n!removeoption a\n!removeoption C\n!removeoption :four:\n!removeoption I mispelld this",
    usage="<existing option>",
)
@commands.check_any(commands.is_owner(), is_admin())
async def removeoption(ctx, *, arg):
    last_poll_message = await get_last_poll_message(ctx)
    if last_poll_message is None:
        await ctx.send(
            "Couldn't find a poll to remove an option from. Did you forget to !startpoll first?", delete_after=10
        )
    embed = last_poll_message.embeds[0]
    if emoji := remove_poll_option(embed, option=arg):
        await asyncio.gather(last_poll_message.edit(embed=embed), last_poll_message.clear_reaction(emoji))
    else:
        await ctx.send(f"{ctx.author.mention} Couldn't remove option '{arg}'", delete_after=10)

@removeoption.error
async def removeoption_error(ctx, error):
    await ctx.message.delete()
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} You have to provide the option to remove when using !removeoption", delete_after=10)


@bot.event
async def on_ready():
    print("Ready")


if __name__ == "__main__":
    try:
        token = os.environ["DISCORD_TOKEN"]
    except KeyError:
        print("You need to specify the environment variable DISCORD_TOKEN before running the bot!", file=sys.stderr)
        sys.exit(1)
    bot.run(token)
