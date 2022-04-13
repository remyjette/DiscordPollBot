import discord
import traceback
from discord import app_commands
from typing import Optional, Union

import bot
from .poll import Poll, PollException

def setup_app_commands(client):
    tree = app_commands.CommandTree(client)

    @client.event
    async def on_ready():
        await tree.sync(guild=bot.TEST_GUILD if client.user == bot.TEST_USER else None)
        print("App commands synced.", flush=True)

    @tree.command(name="startpoll", description="Start a new poll")
    @app_commands.describe(title="The poll's title", set_initial_options="Whether you would like to add initial options to the poll as it's created")
    async def start_poll(
        interaction: discord.Interaction,
        title: str,
        set_initial_options: bool | None
    ):
        await Poll.start(title, interaction)

    @tree.command(name="addoption", description="Add a new option to the latest poll")
    @app_commands.describe(option_name="The new option")
    async def add_option(interaction: discord.Interaction, option_name: str):
        poll = await Poll.get_most_recent(
            interaction.client,
            interaction.channel,
            interaction.user,
        )
        await poll.add_option(option_name)
        await interaction.response.send_message(f"Thanks for adding `{option_name}`. Don't forget to vote for it!", ephemeral=True)

    @tree.command(name="removeoption", description="Remove an option from latest poll")
    async def remove_option(interaction: discord.Interaction):
        await interaction.response.send_message("Rwmove option not implemented")

    @tree.error
    async def on_error(interaction: discord.Interaction, command: Optional[Union[app_commands.Command, app_commands.ContextMenu]], error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        elif isinstance(error, PollException):
            message = str(error)
        else:
            traceback.print_exception(error)
            return
        await interaction.response.send_message("**Error**: " + message, ephemeral=True)

    tree.copy_global_to(guild=bot.TEST_GUILD)
