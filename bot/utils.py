import discord
import re
import bot


class DiscordV8Route(discord.http.Route):
    """A subclass of discord.http.Route that uses the v8 gateway as the base instead.

    discord.http.Route currently uses v8 in the master branch, so assuming that releases and doesn't get reverted this
    can be removed on the next release.

    https://github.com/Rapptz/discord.py/commit/d85805ab6d7a077db303c2bf1670c4948455f3ab
    """

    BASE = "https://discord.com/api/v8"


async def get_or_fetch_user(id):
    try:
        return bot.instance.get_user(id) or await bot.instance.fetch_user(id)
    except discord.NotFound:
        return None


async def get_or_fetch_member(id, guild):
    try:
        return guild.get_member(id) or await guild.fetch_member(id)
    except discord.NotFound:
        return None


async def get_or_fetch_channel(id):
    try:
        return bot.instance.get_channel(id) or await bot.instance.fetch_channel(id)
    except discord.NotFound:
        return None


def remove_mentions(str, guild=None):
    # NOTE: The 'members' intent is currently required for this function to work.
    # TODO: If we don't have Intent.members, we should call fetch_user for each user mentioned and populate a dict in
    # this function for replace_id_with_username to use instead of bot.instance.get_user.

    def replace_id_with_username(id):
        user = bot.instance.get_user(id)
        if not user:
            return f"@{id}"
        return f"@{user.name}#{user.discriminator}"

    def replace_id_with_role(id):
        if guild and (role := guild.get_role(id)):
            return f"@{role.name}"
        else:
            return f"@{id}"

    def replace_id_with_channel(id):
        channel = bot.instance.get_channel(id)
        if not channel:
            return f"#{id}"
        return f"#{channel.name}"

    def remove_mentions_replacement(match):
        if match.group(1) == "@":
            return replace_id_with_username(int(match.group(2)))
        if match.group(1) == "@&":
            return replace_id_with_role(int(match.group(2)))
        if match.group(1) == "#":
            return replace_id_with_channel(int(match.group(2)))

    return re.sub(r"<(@|@&|#)!?(\d+)>", remove_mentions_replacement, str)
