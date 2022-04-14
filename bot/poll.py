import asyncio
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

    async def remove_option(self, option=None, emoji=None):
        assert bool(option) ^ bool(emoji)

        if not emoji and len(option) == 1:
            if option in allowed_emoji:
                emoji = option
                option = None
            elif ord("A") <= (option_ord := ord(option.upper())) <= ord("Z"):
                emoji = chr(ord(EMOJI_A) + option_ord - ord("A"))
                option = None

        def filtered_lines(lines):
            nonlocal emoji
            iterator = iter(lines)
            for line in iterator:
                if emoji and line.startswith(emoji):
                    break
                if option is not None:
                    line_emoji, line_option = line.split(" ", maxsplit=1)
                    if line_option == option:
                        emoji = line_emoji
                        break
                yield line
            yield from iterator

        embed = self.message.embeds[0]

        # Copy the string before we start changing it, so we can return an error if we did nothing
        if embed.description:
            before = embed.description
            new_description = "\n".join(filtered_lines(embed.description.split("\n")))

        if not embed.description or new_description == before:
            message = f"This poll doesn't have an option '{option or emoji}' to remove."
            if option:
                message += " You could also try specifying option's letter instead (`!removeoption A`)"
            raise PollException(message)

        embed.description = new_description

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

    def get_poll_options(self):
        embed = self.message.embeds[0]
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
