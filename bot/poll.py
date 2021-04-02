import asyncio
import discord
import re
import bot
from .emoji import allowed_emoji, EMOJI_A, EMOJI_Z
from .utils import remove_mentions


class PollException(Exception):
    pass


class Poll:
    def __init__(self, poll_message, current_user):
        self.message = poll_message
        self.current_user = current_user

    @property
    def creator(self):
        created_by_field = next(
            (field for field in self.message.embeds[0].fields if field.name == "Poll created by"), None
        )
        if not created_by_field:
            return None
        try:
            created_by_user_id = int(re.search(r"\d+", created_by_field.value).group())
        except TypeError:
            return None

        return bot.instance.get_user(created_by_user_id)  # Need to make this async with a fetch backup

    async def add_option(self, option, reminders_enabled=True):
        embed = self.message.embeds[0]
        emoji = _add_option_to_embed(embed, option)
        await asyncio.gather(self.message.edit(embed=embed), self.message.add_reaction(emoji))
        if not self.current_user:
            return
        # Refresh message to see if user reacted
        def check(payload):
            return (
                payload.message_id == self.message.id
                and payload.user_id == self.current_user.id
                and payload.emoji.name == emoji
            )

        if not reminders_enabled:
            return

        try:
            await bot.instance.wait_for("raw_reaction_add", timeout=30, check=check)
        except asyncio.TimeoutError:
            await self.message.channel.send(
                f"{self.current_user.mention} Thanks for adding `{option}` to the poll, but don't forget to vote for it!",
                delete_after=10,
            )

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
    async def start(cls, channel, creator, settings):
        assert settings.get("title", None)

        embed = discord.Embed()
        embed.title = remove_mentions(settings["title"], guild=channel.guild)
        embed.add_field(name="Poll created by", value=creator.mention, inline=True)
        embed.set_footer(text="Add new options to this poll with /addoption")

        initial_emojis = []
        if "options" in settings:
            for option in settings["options"]:
                if option:
                    try:
                        emoji = _add_option_to_embed(embed, option)
                        initial_emojis.append(emoji)
                    except PollException:
                        # During !startpoll, add_option should only fail if the user provides a duplicate or more than
                        # 20 options. For now, just silently strip duplicates and any options past 20.
                        pass

        message = await channel.send(embed=embed)
        if initial_emojis:
            await asyncio.gather(*(message.add_reaction(emoji) for emoji in initial_emojis))
        return cls(message, creator)

    @classmethod
    async def get_most_recent(cls, channel, current_user, response_on_fail=None):
        message = await channel.history().find(lambda m: m.author == bot.instance.user and len(m.embeds) > 0)
        if message is None:
            if response_on_fail:
                await channel.send(response_on_fail, delete_after=10)
            return None
        return cls(message, current_user)

    @classmethod
    async def get_from_reply(cls, message, current_user, response_on_fail=None):
        if message.reference is None:
            raise RuntimeError("get_from_reply() was called on a message that didn't have a reply")
        # Should also check if the message type is reply. https://github.com/Rapptz/discord.py/issues/6054
        replied_to_message = await message.channel.fetch_message(message.reference.message_id)
        if replied_to_message.author != bot.instance.user or not replied_to_message.embeds:
            if response_on_fail:
                await message.channel.send(response_on_fail, delete_after=10)
            return None
        return cls(replied_to_message, current_user)


def _add_option_to_embed(embed, option):
    if re.search("\((?:added|edited)[^()]*\)$", option):
        raise PollException(
            "Poll options should not contain added/edited information metadata as it will be added by the bot."
        )

    if embed.description == discord.Embed.Empty:
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
            raise PollException(f"Option '{option}' already exists in this poll.")
        # TODO should probably make sure the .split() above worked, that last_seen_emoji is in allowed_emoji

    if last_seen_emoji == EMOJI_Z:
        raise PollException(
            f"Vote option {EMOJI_Z} is already in use. It will need to be removed to add another option."
        )

    new_option_emoji = chr(ord(last_seen_emoji) + 1)

    description_lines.append(new_option_emoji + " " + option)

    embed.description = "\n".join(description_lines)
    return new_option_emoji
