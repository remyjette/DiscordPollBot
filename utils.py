import itertools
import string
from shlex import shlex

EMOJI_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
EMOJI_Z = "\N{REGIONAL INDICATOR SYMBOL LETTER Z}"
NUMBER_TO_EMOJI_UNICODE = "\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}"

allowed_emoji = list(
    itertools.chain(
        (str(number) + NUMBER_TO_EMOJI_UNICODE for number in range(0, 10)),
        (chr(codepoint) for codepoint in range(ord(EMOJI_A), ord(EMOJI_Z) + 1)),
    )
)


def number_to_emoji(num):
    if 1 <= num <= 9:
        return str(num) + NUMBER_TO_EMOJI_UNICODE
    elif 10 <= num < 36:
        return chr(ord(EMOJI_A) + (num - 10))
    else:
        return None


def emoji_to_number(emoji_str, strict=True):
    if (not strict or len(emoji_str) == 3) and len(emoji_str) >= 3 and emoji_str[1:3] == NUMBER_TO_EMOJI_UNICODE:
        # TODO the above check could probably be cleaner
        return int(emoji_str[0])

    if (not strict or len(emoji_str) == 1) and ord(EMOJI_A) <= ord(emoji_str[0]) <= ord(EMOJI_Z):
        return ord(emoji_str[0]) - ord(EMOJI_A) + 10

    return None


def parse_command_args(text):
    lexer = shlex(text, posix=True)
    lexer.whitespace = " "
    lexer.wordchars += string.punctuation
    return dict(word.split("=", maxsplit=1) for word in lexer)
