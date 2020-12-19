import aiohttp
import os
import string
from discord.ext import commands
import bot
from .poll import Poll


_startpoll_slash_command_info = {
    "name": "startpoll",
    "description": "Start a new poll",
    "options": [{"name": "title", "description": "The poll's title", "type": 3, "required": True}],  # type 3 is string
}

assert len(_startpoll_slash_command_info["options"]) <= 10

for i, letter in enumerate(string.ascii_lowercase[: 10 - len(_startpoll_slash_command_info["options"])]):
    _startpoll_slash_command_info["options"].append(
        {
            "name": f"option_{letter}",
            "description": f"The poll's {i + 1}{'st' if i == 0 else 'nd' if i == 1 else 'rd' if i == 2 else 'th'} option",
            "type": 3,  # type 3 is string
            "required": False,
        }
    )

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
            # should probably log if this fails
            await session.post(
                url, headers={"Authorization": f"Bot {bot.instance.http.token}"}, json=_startpoll_slash_command_info
            )

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        if msg["t"] != "INTERACTION_CREATE":
            return
        interaction = msg["d"]
        if interaction["data"]["name"] != "startpoll":
            return
        url = f"{_discord_api_base}/interactions/{interaction['id']}/{interaction['token']}/callback"
        if interaction["type"] == 1:  # Ping
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"type": 1})  # Type 1 is pong
        elif interaction["type"] == 2:  # ApplicationCommand
            # Respond with Acknowledge. This will eat the user's imput but not send a message (as we'll send a message
            # ourselves by calling Poll.start())
            async with aiohttp.ClientSession() as session:
                await session.post(url, json={"type": 2})  # Type 2 is Acknowledge
            settings = {}
            settings["title"] = next(o for o in interaction["data"]["options"] if o["name"] == "title")["value"]

            channel = bot.instance.get_channel(interaction["channel_id"]) or await bot.instance.fetch_channel(
                interaction["channel_id"]
            )
            user = bot.instance.get_user(interaction["member"]["user"]["id"]) or await bot.instance.fetch_user(
                interaction["member"]["user"]["id"]
            )

            if not channel or not user:
                return

            if not settings["title"]:
                # This should never happen as "title" is a required arg, but right now there's a bug in mobile Discord
                # where it's allowing commands to be sent even when missing required args.
                await channel.send(f"{ctx.author.mention} You forgot to provide the poll title!", delete_after=10),
                return

            options_data = sorted(
                (o for o in interaction["data"]["options"] if o["name"].startswith("option_")), key=lambda o: o["name"]
            )
            settings["options"] = [o["value"] for o in options_data]

            await Poll.start(channel, user, settings)
