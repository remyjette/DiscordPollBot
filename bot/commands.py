import asyncio
import discord
import string
from discord.ext import commands
from shlex import shlex

import bot
from .emoji import EMOJI_Z
from .poll import Poll, PollException

required_permissions = discord.Permissions(
    read_messages=True,  # To see commands sent by users
    send_messages=True,  # To send the poll message
    manage_messages=True,  # To clear invalid reacts from users and delete command messages after they are processed
    embed_links=True,  # To embed the poll as a rich content card
    read_message_history=True,  # To find the poll when a user does !addoption or !removeoption
    add_reactions=True,  # To add the initial reactions for users to be able to click on to vote
)

# In arg_types, 'list' is a list of strings
arg_types = {"title": str, "options": list, "new_options_allowed": bool}


def is_admin_check():
    def predicate(ctx):
        return ctx.guild is not None and ctx.author.guild_permissions.administrator

    return commands.check(predicate)


def parse_command_args(text):
    lexer = shlex(text, posix=True)
    lexer.whitespace = " "
    lexer.wordchars += string.punctuation
    return dict(word.split("=", maxsplit=1) for word in lexer)


async def get_poll_for_context(ctx):
    command_str = ctx.prefix + ctx.invoked_with
    if ctx.message.reference is not None:
        # Should also check if the message type is reply. https://github.com/Rapptz/discord.py/issues/6054
        poll = await Poll.get_from_reply(
            ctx.message, response_on_fail=f"{ctx.author.mention} Can't {command_str} that message, it's not a poll!"
        )
    else:
        poll = await Poll.get_most_recent(
            ctx.channel,
            response_on_fail=f"{ctx.author.mention} Couldn't find a poll in this channel for {command_str}. Did you forget to !startpoll first?",
        )
    return poll


class DiscordBotHelpCommand(commands.MinimalHelpCommand):
    def get_ending_note(self):
        return (
            "Like this bot? Add it to your own servers by clicking "
            f"<https://discord.com/oauth2/authorize?client_id={self.context.bot.user.id}"
            f"&scope=bot%20applications.commands&permissions={required_permissions.value}>"
        )

    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page, delete_after=30)


class Commands(commands.Cog):
    def __init__(self):
        bot.instance.help_command.cog = self

    async def cog_check(self, ctx):
        if not ctx.channel.permissions_for(ctx.me).is_superset(required_permissions):
            await ctx.send(
                "Error: Some required permissions are missing. Someone with the 'Manage Server' permission will need"
                " to resolve the issue before this bot can be used.",
                delete_after=20,
            )
            return False
        return True

    async def cog_after_invoke(self, ctx):
        await ctx.message.delete()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            if ctx.command == self.startpoll:
                message = "You forgot to provide the poll title!"
            elif ctx.command == self.addoption:
                message = "You have to provide the new option when using !addoption"
            elif ctx.command == self.removeoption:
                message = "You have to provide the option to remove when using !removeoption"
            await asyncio.gather(
                ctx.message.delete(),
                ctx.send(f"{ctx.author.mention} {message}", delete_after=10),
            )
        if isinstance(error, commands.CheckFailure):
            # If this is the global bot permissions check, we already notified the channel. If this is a user trying
            # to use a command they don't have permissions for, just swallow the exception.
            try:
                await ctx.message.delete()
            except:
                pass
            return
        raise error

    @commands.command()
    @commands.check_any(commands.is_owner(), is_admin_check())
    async def removeallpolls(self, ctx):
        await ctx.channel.purge(check=(lambda m: m.author == ctx.me))

    @commands.command(
        brief="Create a new poll",
        help="Creates a new poll",
        usage="<title> or !startpoll title=Title, options=option1,option2",
    )
    async def startpoll(self, ctx, *, args):
        settings = {}
        if "title=" not in args and any(f"{arg_name}=" in args for arg_name in arg_types):
            await ctx.send(
                f"{ctx.author.mention} When specifying multiple arguments the title argument is required.",
                delete_after=10,
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
        await Poll.start(ctx.channel, ctx.author, settings)

    @commands.command(
        brief="Add an option to an existing poll",
        help=f"Adds a new option to an existing poll.\n\nThere must be fewer than 20 existing options, and {EMOJI_Z} must not already be in use.\n\nExample: !addoption Pizza Bagels",
        usage="<new option>",
    )
    async def addoption(self, ctx, *, arg):
        if not (poll := await get_poll_for_context(ctx)):
            return
        try:
            await poll.add_option(arg)
        except PollException as e:
            await ctx.send(f"{ctx.author.mention} Error: {e}", delete_after=10)

    @commands.command(
        brief="Remove an option from an existing poll",
        help=f"Removes an option to an existing poll.\n\nYou can specify either the letter/number for the option, use the emoji, or just name the text of the option.\n\nExamples:\n!removeoption 3\n!removeoption a\n!removeoption C\n!removeoption :four:\n!removeoption I mispelld this",
        usage="<existing option>",
    )
    @commands.check_any(commands.is_owner(), is_admin_check())
    async def removeoption(self, ctx, *, arg):
        if not (poll := await get_poll_for_context(ctx)):
            return
        try:
            await poll.remove_option(option=arg)
        except PollException as e:
            await ctx.send(f"{ctx.author.mention} Error: {e}", delete_after=10)
