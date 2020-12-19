import asyncio
import discord
import string
from discord.ext import commands
from shlex import shlex

import bot
from .emoji import EMOJI_Z
from .poll_options import add_poll_option, remove_poll_option, PollOptionException

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


def get_last_poll_message(ctx):
    return ctx.history().find(lambda m: m.author == ctx.me and len(m.embeds) > 0)


def is_admin_check():
    def predicate(ctx):
        return ctx.guild is not None and ctx.author.guild_permissions.administrator

    return commands.check(predicate)


def parse_command_args(text):
    lexer = shlex(text, posix=True)
    lexer.whitespace = " "
    lexer.wordchars += string.punctuation
    return dict(word.split("=", maxsplit=1) for word in lexer)


class DiscordBotHelpCommand(commands.MinimalHelpCommand):
    def get_ending_note(self):
        return (
            "Like this bot? Add it to your own servers by clicking "
            + discord.utils.oauth_url(self.context.bot.user.id, required_permissions)
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

        embed = discord.Embed()
        if "title" in settings:
            embed.title = settings["title"]
        embed.add_field(name="Poll created by", value=ctx.author.mention, inline=True)
        embed.set_footer(text="Add new options to this poll with !addoption")

        initial_emojis = []
        if "options" in settings:
            for option in settings["options"]:
                if option:
                    try:
                        emoji = add_poll_option(embed, option)
                        initial_emojis.append(emoji)
                    except PollOptionException:
                        # During !startpoll, add_option should only fail if the user provides a duplicate or more than
                        # 20 options. For now, just silently strip duplicates and any options past 20.
                        pass

        message = await ctx.send(embed=embed)
        if initial_emojis:
            await asyncio.gather(*(message.add_reaction(emoji) for emoji in initial_emojis))

    @commands.command(
        brief="Add an option to an existing poll",
        help=f"Adds a new option to an existing poll.\n\nThere must be fewer than 20 existing options, and {EMOJI_Z} must not already be in use.\n\nExample: !addoption Pizza Bagels",
        usage="<new option>",
    )
    async def addoption(self, ctx, *, arg):
        if ctx.message.reference is not None:
            # Should also check if the message type is reply. https://github.com/Rapptz/discord.py/issues/6054
            poll_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if poll_message.author != ctx.me or not poll_message.embeds:
                await ctx.send(
                    f"{ctx.author.mention} Can't !addoption to that message, it's not a poll!", delete_after=10
                )
                return
        else:
            poll_message = await get_last_poll_message(ctx)
            if poll_message is None:
                await ctx.send(
                    f"{ctx.author.mention} Couldn't find a poll to an option to. Did you forget to !startpoll first?",
                    delete_after=10,
                )
                return
        embed = poll_message.embeds[0]
        try:
            emoji = add_poll_option(embed, arg)
            await asyncio.gather(poll_message.edit(embed=embed), poll_message.add_reaction(emoji))
        except PollOptionException as e:
            await ctx.send(f"{ctx.author.mention} Error: {e}", delete_after=10)

    @commands.command(
        brief="Remove an option from an existing poll",
        help=f"Removes an option to an existing poll.\n\nYou can specify either the letter/number for the option, use the emoji, or just name the text of the option.\n\nExamples:\n!removeoption 3\n!removeoption a\n!removeoption C\n!removeoption :four:\n!removeoption I mispelld this",
        usage="<existing option>",
    )
    @commands.check_any(commands.is_owner(), is_admin_check())
    async def removeoption(self, ctx, *, arg):
        if ctx.message.reference is not None:
            # Should also check if the message type is reply. https://github.com/Rapptz/discord.py/issues/6054
            poll_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if poll_message.author != ctx.me or not poll_message.embeds:
                await ctx.send(
                    f"{ctx.author.mention} Can't !addoption to that message, it's not a poll!", delete_after=10
                )
                return
        else:
            poll_message = await get_last_poll_message(ctx)
            if poll_message is None:
                await ctx.send(
                    f"{ctx.author.mention} Couldn't find a poll to remove an option from. Did you forget to !startpoll first?",
                    delete_after=10,
                )
                return
        embed = poll_message.embeds[0]
        try:
            emoji = remove_poll_option(embed, option=arg)
            await asyncio.gather(poll_message.edit(embed=embed), poll_message.clear_reaction(emoji))
        except PollOptionException as e:
            await ctx.send(f"{ctx.author.mention} Error: {e}", delete_after=10)
