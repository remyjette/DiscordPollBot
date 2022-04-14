import asyncio
import discord
import re
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
    def __init__(self, poll_message, current_user):
        self.message = poll_message
        self.current_user = current_user
        # self._creator = None

    # async def ensure_current_user_is_member(self):
    #     self.current_user = await self.client.user_to_member(self.current_user, self.message.guild)

    # async def get_creator(self):
    #     if self._creator:
    #         return self._creator

    #     # If this poll was created with /startpoll, the creator is available by checking the Message's interaction
    #     # property. If it's created with !startpoll, the creator is a field in the Poll embed.
    #     # Unfortunately the discord.py Message object doesn't save the interaction property from the API object right
    #     # now, so we'll have to do a separate API call to get it.
    #     # Since an API call is required to check for an interaction, we check for the embed first.

    #     created_by_user_id = None

    #     # created_by_field = next(
    #     #     (field for field in self.message.embeds[0].fields if field.name == "Poll created by"), None
    #     # )
    #     # if created_by_field:
    #     #     try:
    #     #         created_by_user_id = int(re.search(r"\d+", created_by_field.value).group())
    #     #     except TypeError:
    #     #         pass

    #     # if not created_by_user_id:
    #     #     route = discord.http.Route("GET", f"/channels/{self.message.channel.id}/messages/{self.message.id}")
    #     #     message_data = await bot.instance.http.request(route)
    #     #     try:
    #     #         created_by_user_id = message_data["interaction"]["user"]["id"]
    #     #     except KeyError:
    #     #         pass

    #     if created_by_user_id is None:
    #         return None

    #     #self._creator = await self.client.get_or_fetch_member(created_by_user_id, self.message.guild)

    #     return self._creator

    async def add_option(self, option):
        embed = self.message.embeds[0]
        emoji = _add_option_to_embed(embed, option)
        await asyncio.gather(self.message.edit(embed=embed), self.message.add_reaction(emoji))
        if not self.current_user:
            return

    async def remove_option(self, option=None, emoji=None):
        assert bool(option) ^ bool(emoji)

        await self.ensure_current_user_is_member()

        if not (
            self.current_user == await self.get_creator()
            or self.current_user.permissions_in(self.message.channel).manage_messages
            or self.current_user == (await self.client.application_info()).owner
        ):
            # TODO move this to app_commands.py
            raise PollException(
                "Only the poll creator or someone with 'Manage Messages' permissions can remove a poll option."
            )

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
        client: discord.Client,
        channel: discord.abc.GuildChannel | discord.PartialMessageable | discord.Thread | None,
        current_user,
    ):
        async for message in channel.history():
            if message.author == client.user and len(message.embeds) > 0:
                return cls(message, current_user)
        raise PollException(f"No poll was found in the channel #{channel.name}.")

    def get_poll_options(self):
        embed = self.message.embeds[0]
        return [PollOption(*line.split(" ", maxsplit=1)) for line in embed.description.split("\n")]

    # @classmethod
    # async def get_from_reply(cls, client: discord.Client, message, current_user, response_on_fail=None):
    #     if message.reference is None:
    #         raise RuntimeError("get_from_reply() was called on a message that didn't have a reply")
    #     # Should also check if the message type is reply. https://github.com/Rapptz/discord.py/issues/6054
    #     replied_to_message = await message.channel.fetch_message(message.reference.message_id)
    #     if replied_to_message.author != client.user or not replied_to_message.embeds:
    #         if response_on_fail:
    #             await message.channel.send(response_on_fail, delete_after=10)
    #         return None
    #     return cls(replied_to_message, current_user)


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
