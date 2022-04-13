from code import interact
import discord
import traceback
from discord import app_commands

import bot
from .utils import remove_mentions
from .poll import Poll, PollException


class PollSettingsModal(discord.ui.Modal, title="Create a poll"):
    def __init__(self, title: str, original_interaction: discord.Interaction):
        super().__init__()
        self.original_interaction = original_interaction
        self.title = title
        for i in range(0, 5):
            item = discord.ui.TextInput(label=f"Option {i + 1}", required=False)
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.original_interaction.followup.send(embed=Poll.create_poll_embed(self.title))
        initial_poll_options = [
            stripped_value for item in self.children if (stripped_value := item.value.strip()) != ""
        ]
        print(initial_poll_options)  # TODO Add these to the poll


def setup_app_commands(client: discord.Client):
    tree = app_commands.CommandTree(client)

    @client.event
    async def on_ready():
        await tree.sync(guild=bot.TEST_GUILD if client.user.id == bot.TEST_USER.id else None)
        print("App commands synced.", flush=True)

    @tree.command(name="startpoll", description="Start a new poll")
    @app_commands.describe(
        title="The poll's title",
        set_initial_options="Whether you would like to add initial options to the poll as it's created",
    )
    async def start_poll(interaction: discord.Interaction, title: str, set_initial_options: bool | None):
        title = remove_mentions(title, client=interaction.client, guild=interaction.guild)
        if set_initial_options:
            await interaction.response.send_modal(PollSettingsModal(title, interaction))
        else:
            await interaction.response.send_message(embed=Poll.create_poll_embed(title))

    @tree.command(name="addoption", description="Add a new option to the latest poll")
    @app_commands.describe(option_name="The new option")
    async def add_option(interaction: discord.Interaction, option_name: str):
        poll = await Poll.get_most_recent(
            interaction.client,
            interaction.channel,
            interaction.user,
        )
        await poll.add_option(option_name)
        await interaction.response.send_message(
            f"Thanks for adding `{option_name}`. Don't forget to vote for it!", ephemeral=True
        )

    @tree.command(name="removeoption", description="Remove an option from latest poll")
    async def remove_option(interaction: discord.Interaction):
        await interaction.response.send_message("Rwmove option not implemented", ephemeral=True)

    @tree.error
    async def on_error(
        interaction: discord.Interaction,
        command: app_commands.Command | app_commands.ContextMenu | None,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command."
        elif isinstance(error, PollException):
            message = str(error)
        else:
            traceback.print_exception(error)
            return
        await interaction.response.send_message("**Error**: " + message, ephemeral=True)

    tree.copy_global_to(guild=bot.TEST_GUILD)
