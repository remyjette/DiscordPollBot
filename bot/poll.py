import asyncio
from typing import List
import discord
import re
import functools
from dataclasses import dataclass

from .utils import remove_mentions
from .emoji import allowed_emoji, EMOJI_A, EMOJI_Z


class PollException(discord.app_commands.AppCommandError):
    pass


@dataclass(frozen=True)
class PollOption:
    emoji: str
    label: str


class Poll:
    def __init__(self, poll_message: discord.Message):
        self.message = poll_message

    @property
    def creator(self):
        return self.message.interaction.user

    async def add_option(self, option):
        embed = self.message.embeds[0]
        emoji = _add_option_to_embed(embed, option)
        await asyncio.gather(self.message.edit(embed=embed), self.message.add_reaction(emoji))

    async def remove_option(self, option: str):
        emoji = None

        def filtered_lines(lines):
            nonlocal emoji
            iterator = iter(lines)
            for line in iterator:
                line_emoji, line_option = line.split(" ", maxsplit=1)
                if line_option == option:
                    emoji = line_emoji
                    break
                yield line
            else:
                raise PollException(f"This poll no longer has an option '{option}' to remove.")
            yield from iterator

        embed = self.message.embeds[0]

        if not embed.description:
            raise PollException("This poll doesn't have any options to remove.")

        embed.description = "\n".join(filtered_lines(embed.description.split("\n")))

        tasks = [self.message.edit(embed=embed)]
        if discord.utils.get(self.message.reactions, emoji=emoji):
            tasks.append(self.message.clear_reaction(emoji))
        await asyncio.gather(*tasks)

    @classmethod
    def create_poll_embed(cls, title: str):
        embed = discord.Embed()
        embed.title = title
        embed.set_footer(text="Add new options to this poll with /addoption")
        return embed

    @classmethod
    async def get_most_recent(
        cls,
        client_user: discord.ClientUser,
        channel: discord.abc.GuildChannel | discord.PartialMessageable | discord.Thread | None,
    ):
        async for message in channel.history():
            if message.author == client_user and len(message.embeds) > 0:
                return cls(message)
        raise PollException(f"No poll was found in the channel #{channel.name}.")

    def get_poll_options(self) -> List[PollOption]:
        if len(self.message.embeds) == 0:
            raise RuntimeError("This poll doesn't have any embeds!")
        embed = self.message.embeds[0]
        if not embed.description:
            return list()
        return [PollOption(*line.split(" ", maxsplit=1)) for line in embed.description.split("\n")]


def _add_option_to_embed(embed, option):
    if re.search("\((?:added|edited)[^()]*\)$", option):
        raise PollException(
            "Poll options should not contain added/edited information metadata as it will be added by the bot."
        )

    if embed.description == None:
        new_option_emoji = EMOJI_A
        embed.description = new_option_emoji + " " + option
        return new_option_emoji

    description_lines = embed.description.split("\n")

    if len(description_lines) >= 20:
        raise PollException(
            "Discord only allows 20 reactions per message. One will need to be removed to add another option."
        )

    # Make sure we don't already have this option
    for line in description_lines:
        last_seen_emoji, last_seen_option = line.split(" ", maxsplit=1)
        if option == last_seen_option:
            raise PollException(f"Option `{option}` already exists in this poll.")
        # TODO should probably make sure the .split() above worked, that last_seen_emoji is in allowed_emoji

    if last_seen_emoji == EMOJI_Z:
        raise PollException(
            f"Vote option {EMOJI_Z} is already in use. It will need to be removed to add another option."
        )

    new_option_emoji = chr(ord(last_seen_emoji) + 1)

    description_lines.append(new_option_emoji + " " + option)

    embed.description = "\n".join(description_lines)
    return new_option_emoji
