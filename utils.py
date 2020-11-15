EMOJI_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
EMOJI_Z = "\N{REGIONAL INDICATOR SYMBOL LETTER Z}"
NUMBER_TO_EMOJI_UNICODE = "\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}"

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
