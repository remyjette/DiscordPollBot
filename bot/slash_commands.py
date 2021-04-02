import asyncio
import os
import string
from enum import IntEnum

import aiohttp
from discord.ext import commands

import bot
from .poll import Poll, PollException


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
        "description": "(Admin only) Remove option from latest poll (To remove from previous poll reply with !removeoption)",
        "options": [
            {
                "name": "option_name",
                "description": "The new option",
                "type": ApplicationCommandOptionType.STRING,
                "required": True,
            }
        ],
    },
]

_discord_api_base = "https://discord.com/api/v8"


class SlashCommands(commands.Cog):
    """A discord.ext.commands.Cog that will listen to events to handle Slash Commands

    discord.py doesn't yet support slash commands (https://github.com/Rapptz/discord.py/issues/6149). Until it does, we
    can work around that by simply making the requests and handling the events manually.

    Once discord.py adds full support for Slash Commands this should be rewritten to use that API.
    """

    @commands.Cog.listener()
    async def on_ready(self):
        url = f"{_discord_api_base}/applications/{bot.instance.user.id}"
        # If this is PollBotDev, use the guild-specific endpoint for the test server which will update instantly.
        # Otherwise use the global endpoint. Should probably clean this up.
        url += "/commands" if bot.instance.user.id != 777347007664750592 else f"/guilds/714999738318979163/commands"
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(
                *(
                    session.post(
                        url,
                        headers={"Authorization": f"Bot {bot.instance.http.token}"},
                        json=command,
                        raise_for_status=True,
                    )
                    for command in _application_commands
                )
            )

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        if msg["t"] != "INTERACTION_CREATE":
            return
        interaction = msg["d"]

        url = f"{_discord_api_base}/interactions/{interaction['id']}/{interaction['token']}/callback"
        if interaction["type"] == 1:  # Ping
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"type": 1})  # Type 1 is pong
        elif interaction["type"] == 2:  # ApplicationCommand
            channel = bot.instance.get_channel(interaction["channel_id"]) or await bot.instance.fetch_channel(
                interaction["channel_id"]
            )
            user = bot.instance.get_user(interaction["member"]["user"]["id"]) or await bot.instance.fetch_user(
                interaction["member"]["user"]["id"]
            )
            if not channel or not user:
                raise RuntimeError("Could not find channel or user for interaction response.")

            if interaction["data"]["name"] == "startpoll":
                response_message = await self._handle_startpoll(interaction, channel, user)
            elif interaction["data"]["name"] == "addoption":
                response_message = await self._handle_addoption(interaction, channel, user)
            elif interaction["data"]["name"] == "removeoption":
                response_message = await self._handle_removeoption(interaction, channel, user)
            else:
                raise RuntimeError(f"Didn't understand interaction {interaction['data']['name']}.")

            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"type": 4, "data": {"content": response_message, "flags": 64}})

    async def _handle_startpoll(self, interaction, channel, user):
        settings = {}
        settings["title"] = next(o for o in interaction["data"]["options"] if o["name"] == "title")["value"]

        if not settings["title"]:
            # This should never happen as "title" is a required arg, but just in case...
            return "You forgot to provide the poll title!"

        options_data = sorted(
            (o for o in interaction["data"]["options"] if o["name"].startswith("option_")), key=lambda o: o["name"]
        )
        settings["options"] = [o["value"] for o in options_data]

        await Poll.start(channel, user, settings)

        return "Poll created successfully!"

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
            return "You forgot to provide the poll option!"
        try:
            await poll.add_option(option, reminders_enabled=False)
            return f"Thanks for adding `{option}`. Don't forget to vote for it!"
        except PollException as e:
            return f"Error: {e}"

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
            return "You forgot to provide the poll option!"
        try:
            await poll.remove_option(option)
            return f"`{option}` has been removed."
        except PollException as e:
            return f"Error: {e}"
