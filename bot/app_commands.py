from code import interact
from typing import List
import discord
import traceback
from discord import app_commands

import bot
from .utils import remove_mentions
from .poll import Poll, PollException, PollOption


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


class RemovePollOptionDropdownView(discord.ui.View):
    class RemovePollOptionDropdown(discord.ui.Select):
        def __init__(self, original_interaction: discord.Interaction, poll: Poll):
            self.original_interaction = original_interaction
            self.poll = poll
            select_options = [
                discord.SelectOption(label=option.label, emoji=option.emoji) for option in poll.get_poll_options()
            ]
            if not select_options:
                raise PollException("This poll does not have any options to remove.")
            super().__init__(
                placeholder="Chose an option to remove...", min_values=1, max_values=1, options=select_options
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            await self.original_interaction.edit_original_message(
                content=f"Are you sure you want to remove '{self.values[0]}'?",
                view=RemovePollOptionConfirmView(self.original_interaction, self.poll, self.values[0]),
            )

    def __init__(self, original_interaction: discord.Interaction, poll: Poll):
        super().__init__()
        self.add_item(self.RemovePollOptionDropdown(original_interaction, poll))


class RemovePollOptionConfirmView(discord.ui.View):
    def __init__(self, original_interaction: discord.Interaction, poll: Poll, chosen_option: str):
        super().__init__()
        self.original_interaction = original_interaction
        self.chosen_option = chosen_option
        self.poll = poll

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.original_interaction.edit_original_message(content=f"Remove poll option cancelled.", view=None)
        self.stop()

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.poll.remove_option(self.chosen_option)
        await self.original_interaction.edit_original_message(
            content=f"Option '{self.chosen_option}' has been removed.", view=None
        )
        self.stop()


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
            interaction.client.user,
            interaction.channel,
        )
        await poll.add_option(option_name)
        await interaction.response.send_message(
            f"Thanks for adding `{option_name}`. Don't forget to vote for it!", ephemeral=True
        )

    @tree.command(name="removeoption", description="Remove an option from latest poll")
    async def remove_option(interaction: discord.Interaction):
        # TODO check permissions
        # if not (
        #     self.current_user == await self.get_creator()
        #     or self.current_user.permissions_in(self.message.channel).manage_messages
        #     or self.current_user == (await self.client.application_info()).owner
        # ):
        #     raise PollException(
        #         "Only the poll creator or someone with 'Manage Messages' permissions can remove a poll option."
        #     )

        poll = await Poll.get_most_recent(interaction.client.user, interaction.channel)
        await interaction.response.send_message(view=RemovePollOptionDropdownView(interaction, poll), ephemeral=True)

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
