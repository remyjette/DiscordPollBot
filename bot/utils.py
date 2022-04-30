import discord
import re


def remove_mentions(str, *, client: discord.Client, guild=None):
    # NOTE: The 'members' intent is currently required for this function to work.
    # TODO: If we don't have Intent.members, we should call fetch_user for each user mentioned and populate a dict in
    # this function for replace_id_with_username to use instead of client.get_user.

    def replace_id_with_username(id):
        user = client.get_user(id)
        if not user:
            return f"@{id}"
        return f"@{user.name}#{user.discriminator}"

    def replace_id_with_role(id):
        if guild and (role := guild.get_role(id)):
            return f"@{role.name}"
        else:
            return f"@{id}"

    def replace_id_with_channel(id):
        channel = client.get_channel(id)
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
