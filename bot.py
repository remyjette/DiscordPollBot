#!/usr/bin/env python3

import asyncio
import base64
import discord
import json
import string
import sys
import zlib
from discord.ext import commands
from shlex import shlex

import config

required_permissions = discord.Permissions(
    read_messages=True,
    send_messages=True,
    manage_messages=True,
    embed_links=True,
    read_message_history=True,
    add_reactions=True,
)

# permissions: send messages, manage messages, add reactions, read message history

# TODOS:
# 1) what if I want a comma in a vote option?
# 2) Complain if we don't have permissions

# In arg_types, 'list' is a list of strings
arg_types = {"title": str, "vote_options": list, "new_options_allowed": bool}

EMOJI_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
EMOJI_Z = "\N{REGIONAL INDICATOR SYMBOL LETTER Z}"
NUMBER_TO_EMOJI_UNICODE = "\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}"

class MyHelpCommand(commands.MinimalHelpCommand):
    def get_ending_note(self):
        return f"Like this bot? Add it to your own servers by clicking <https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions={required_permissions.value}>"

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page, delete_after=30)

bot = commands.Bot(
    command_prefix="!",
    help_command=MyHelpCommand(),
    intents=discord.Intents(guilds=True, guild_reactions=True, messages=True, members=True),
)


def is_admin():
    def predicate(ctx):
        return ctx.guild is not None and ctx.author.guild_permissions.administrator

    return commands.check(predicate)


@bot.command()
@commands.check_any(commands.is_owner(), is_admin())
async def removeallpolls(ctx):
    await ctx.channel.purge(check=(lambda m: m.author == ctx.me))


def serialize(obj):
    return base64.b64encode(zlib.compress(json.dumps(obj, separators=(",", ":")).encode())).decode()


def deserialize(data):
    return json.loads(zlib.decompress(base64.b64decode(data.encode())).decode())


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


def remove_poll_option(embed, option_string):
    if emoji_to_number(option_string) is not None:
        emoji = option_string
    elif len(option_string) == 1 and option_string.isdigit():
        emoji = option_string + NUMBER_TO_EMOJI_UNICODE
    elif len(option_string) == 1 and ord("A") <= (option_ord := ord(option_string.upper())) <= ord("Z"):
        emoji = chr(ord(EMOJI_A) + option_ord - ord("A"))
    else:
        emoji = None

    def filtered_lines(lines):
        nonlocal emoji
        iterator = iter(lines)
        for line in iterator:
            if emoji and line.startswith(emoji):
                break
            line_emoji, line_option = line.split(" ", maxsplit=1)
            if line_option == option_string:
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


def create_poll_embed_from_settings(settings):
    embed = discord.Embed()
    if "title" in settings:
        embed.title = settings["title"]
    if "vote_options" in settings:
        for option in settings["vote_options"]:
            if option:
                add_poll_option(embed, option)
    return embed


def number_to_emoji(num):
    if 1 <= num <= 9:
        return str(num) + NUMBER_TO_EMOJI_UNICODE
    elif 10 <= num < 36:
        return chr(ord(EMOJI_A) + (num - 10))
    else:
        return None


def emoji_to_number(emoji_str, strict=True):
    if (not strict or len(emoji_str) == 3) and len(emoji_str) >= 3 and emoji_str[1:3] == NUMBER_TO_EMOJI_UNICODE:
        # TODO the above check could probably be cleaner
        return int(emoji_str[0])

    if (not strict or len(emoji_str) == 1) and ord(EMOJI_A) <= ord(emoji_str[0]) <= ord(EMOJI_Z):
        return ord(emoji_str[0]) - ord(EMOJI_A) + 10

    return None


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


@bot.after_invoke
async def cleanup_command(ctx):
    await ctx.message.delete()


@bot.command(
    brief="Create a new poll",
    help="Creates a new poll",
    usage="<title> or !startpoll title=Title, vote_options=option1,option2",
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
                await ctx.send(f"{ctx.author.mention} Did not understand the option '{name}'", delete_after=10)
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

    embed = create_poll_embed_from_settings(settings)

    # TODO avoid awaiting on the flatten
    past_poll_messages = await ctx.history().filter(lambda m: m.author == ctx.me and len(m.embeds) > 0).flatten()
    await asyncio.gather(ctx.send(embed=embed), *[message.clear_reactions() for message in past_poll_messages])


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


@bot.command(
    brief="Remove an option from an existing poll",
    help=f"Removes an option to an existing poll.\n\nYou can specify either the letter/number for the option, use the emoji, or just name the text of the option.\n\nExamples:\n!removeoption 3\n!removeoption a\n!removeoption C\n!removeoption :four:\n!removeoption I mispelld this",
    usage="<existing option>",
)
async def removeoption(ctx, *, arg):
    last_poll_message = await get_last_poll_message(ctx)
    if last_poll_message is None:
        await ctx.send(
            "Couldn't find a poll to remove an option from. Did you forget to !startpoll first?", delete_after=10
        )
    embed = last_poll_message.embeds[0]
    if emoji := remove_poll_option(embed, arg):
        await asyncio.gather(last_poll_message.edit(embed=embed), last_poll_message.clear_reaction(emoji))
    else:
        await ctx.send(f"{ctx.author.mention} Couldn't remove option '{arg}'", delete_after=10)


@bot.event
async def on_ready():
    print("Ready")


if __name__ == "__main__":
    bot.run(config.token)
