import asyncio
import discord
import os
import string
from enum import IntEnum

from discord.ext import commands

import bot
from .poll import Poll, PollException
from .utils import DiscordV8Route, get_or_fetch_channel, get_or_fetch_member


class ApplicationCommandOptionType(IntEnum):
    """See https://discord.com/developers/docs/interactions/slash-commands#applicationcommandoptiontype"""

    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8


_startpoll_application_command = {
    "name": "startpoll",
    "description": "Start a new poll",
    "options": [
        {
            "name": "title",
            "description": "The poll's title",
            "type": ApplicationCommandOptionType.STRING,
            "required": True,
        }
    ],
}

assert len(_startpoll_application_command["options"]) <= 25

for i, letter in enumerate(string.ascii_lowercase[: 25 - len(_startpoll_application_command["options"])]):
    _startpoll_application_command["options"].append(
        {
            "name": f"option_{letter}",
            "description": f"The poll's {i + 1}{'st' if i == 0 else 'nd' if i == 1 else 'rd' if i == 2 else 'th'} option",
            "type": ApplicationCommandOptionType.STRING,
            "required": False,
        }
    )

_application_commands = [
    _startpoll_application_command,
    {
        "name": "addoption",
        "description": "Add a new option to the latest poll (To add to a previous poll reply to that poll with !addoption)",
        "options": [
            {
                "name": "option_name",
                "description": "The new option",
                "type": ApplicationCommandOptionType.STRING,
                "required": True,
            }
        ],
    },
    {
        "name": "removeoption",
        "description": "Remove an option from latest poll (To remove from a previous poll reply with !removeoption).",
        "options": [
            {
                "name": "option_name",
                "description": "The option to remove. Accepts the option letter or the option text.",
                "type": ApplicationCommandOptionType.STRING,
                "required": True,
            }
        ],
    },
]


class SlashCommands(commands.Cog):
    """A discord.ext.commands.Cog that will listen to events to handle Slash Commands

    discord.py doesn't yet support slash commands (https://github.com/Rapptz/discord.py/issues/6149). Until it does, we
    can work around that by simply making the requests and handling the events manually.

    Once discord.py adds full support for Slash Commands this should be rewritten to use that API.
    """

    @commands.Cog.listener()
    async def on_ready(self):
        url = f"/applications/{bot.instance.user.id}"
        # Global commands are cached for up to an hour, and have a rate limit of 200 application command creates per
        # day. For testing, Discord recommends using Guild commands instead which update instantly and don't have the
        # same rate limit. So, detect if this is the dev account and if so create the commands as Guild commands on
        # the test server instead.
        url += "/commands" if bot.instance.user.id != 777347007664750592 else "/guilds/714999738318979163/commands"

        # Before posting changes to our currently registered app commands, retrieve the current list so that we can
        # delete any that might have been added by a previous version of this bot that are no longer in use.
        existing_commands_data = await bot.instance.http.request(DiscordV8Route("GET", url))

        command_names = [command["name"] for command in _application_commands]

        await asyncio.gather(
            *(
                bot.instance.http.request(DiscordV8Route("DELETE", f"{url}/{command['id']}"))
                for command in existing_commands_data
                if command["name"] not in command_names
            ),
            *(
                bot.instance.http.request(DiscordV8Route("POST", url), json=command)
                for command in _application_commands
            ),
        )

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        if msg["t"] != "INTERACTION_CREATE":
            return
        interaction = msg["d"]

        url = f"/interactions/{interaction['id']}/{interaction['token']}/callback"
        if interaction["type"] == 1:  # Ping
            await bot.instance.http.request(DiscordV8Route("POST", url), json={"type": 1})  # Type 1 is pong
            return
        elif interaction["type"] == 2:  # ApplicationCommand
            try:
                channel = await get_or_fetch_channel(interaction["channel_id"])
                user = await get_or_fetch_member(interaction["member"]["user"]["id"], channel.guild)
                if not channel or not user:
                    # This shouldn't happen. If it's a permissions issue, we should get a Forbidden exception instead.
                    raise RuntimeError("Could not find channel or user for interaction response.")

                if interaction["data"]["name"] == "startpoll":
                    await self._handle_startpoll(interaction, channel, user, url)
                    return
                elif interaction["data"]["name"] == "addoption":
                    response_message = await self._handle_addoption(interaction, channel, user)
                elif interaction["data"]["name"] == "removeoption":
                    response_message = await self._handle_removeoption(interaction, channel, user)
                else:
                    raise RuntimeError(f"Didn't understand interaction {interaction['data']['name']}.")
            except discord.Forbidden as e:
                response_message = (
                    "**Error:** This bot does not have permissions to perform that action here. Please talk to a server"
                    " administrator."
                )

            await self._post_slash_command_reponse(url, response_message, ephemeral=True)

    async def _handle_startpoll(self, interaction, channel, user, url):
        settings = {}
        settings["title"] = next(o for o in interaction["data"]["options"] if o["name"] == "title")["value"]

        if not settings["title"]:
            # This should never happen as "title" is a required arg, but just in case...
            await self._post_slash_command_reponse(
                url, "**Error**: You forgot to provide the poll title!", ephemeral=True
            )
            return

        options_data = sorted(
            (o for o in interaction["data"]["options"] if o["name"].startswith("option_")), key=lambda o: o["name"]
        )
        settings["options"] = [o["value"] for o in options_data]

        async def post_poll_fn(embed):
            await self._post_slash_command_reponse(url, embed, ephemeral=False)
            # The ineraction.id is different from the message that appears in the channel, and the POST to update it
            # returns a 204 No Content. To get the message ID, send a GET request to the @original endpoint for this
            # interaction.
            webhook_message_data = await bot.instance.http.request(
                DiscordV8Route("GET", f"/webhooks/{bot.instance.user.id}/{interaction['token']}/messages/@original")
            )
            message = await channel.fetch_message(webhook_message_data["id"])
            return Poll(message, user)

        await Poll.start(channel, user, settings, post_poll_fn)

    async def _handle_addoption(self, interaction, channel, user):
        poll = await Poll.get_most_recent(
            channel,
            current_user=user,
            response_on_fail=f"{user.mention} Couldn't find a poll in this channel for /addoption. Did you forget to /startpoll first?",
        )
        assert len(interaction["data"]["options"]) == 1
        option = interaction["data"]["options"][0]["value"]
        if not option:
            # This should never happen as "option" is a required arg, but just in case...
            return "**Error**: You forgot to provide the poll option!"
        try:
            await poll.add_option(option, reminders_enabled=False)
            return f"Thanks for adding `{option}`. Don't forget to vote for it!"
        except PollException as e:
            return f"**Error**: {e}"

    async def _handle_removeoption(self, interaction, channel, user):
        poll = await Poll.get_most_recent(
            channel,
            current_user=user,
            response_on_fail=f"{user.mention} Couldn't find a poll in this channel for /removeoption. Did you forget to /startpoll first?",
        )
        assert len(interaction["data"]["options"]) == 1
        option = interaction["data"]["options"][0]["value"]
        if not option:
            # This should never happen as "option" is a required arg, but just in case...
            return "**Error**: You forgot to provide the poll option!"
        try:
            await poll.remove_option(option)
            return f"`{option}` has been removed."
        except PollException as e:
            return f"**Error**: {e}"

    async def _post_slash_command_reponse(self, url, message, ephemeral=True):
        data = {"type": 4, "data": {}}

        if isinstance(message, discord.Embed):
            data["data"]["embeds"] = [message.to_dict()]
        else:
            data["data"]["content"] = message

        if ephemeral:
            data["data"]["flags"] = 64

        await bot.instance.http.request(DiscordV8Route("POST", url), json=data)
