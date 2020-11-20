import discord
from utils import EMOJI_A, EMOJI_Z, NUMBER_TO_EMOJI_UNICODE, emoji_to_number, number_to_emoji


def add_poll_option(embed, option):
    if embed.description == discord.Embed.Empty:
        new_option_emoji = number_to_emoji(1)
        embed.description = new_option_emoji + " " + option
        return new_option_emoji

    description_lines = embed.description.split("\n")

    if len(description_lines) >= 20:
        # Discord has a limit of 20 reactions per message. If we're already at 20, one will need to be removed first.
        return None

    # Make sure we don't already have this option
    for line in description_lines:
        last_seen_emoji, last_seen_option = line.split(" ", maxsplit=1)
        if option == last_seen_option:
            return None

    if last_seen_emoji == EMOJI_Z:
        # We have no more letters to use, so no more options can be added to this poll even if options are removed.
        return None

    new_option_emoji = number_to_emoji(emoji_to_number(last_seen_emoji) + 1)
    assert new_option_emoji is not None

    description_lines.append(new_option_emoji + " " + option)

    embed.description = "\n".join(description_lines)
    return new_option_emoji


def remove_poll_option(embed, option=None, emoji=None):
    assert option or emoji

    if not emoji:
        if emoji_to_number(option) is not None:
            emoji = option
            option = None
        elif len(option) == 1 and option.isdigit():
            emoji = option + NUMBER_TO_EMOJI_UNICODE
            option = None
        elif len(option) == 1 and ord("A") <= (option_ord := ord(option.upper())) <= ord("Z"):
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

    # Copy the string before we start changing it, so we can return an error if we did nothing
    before = embed.description
    embed.description = "\n".join(filtered_lines(embed.description.split("\n")))

    if embed.description == before:
        return None

    return emoji
