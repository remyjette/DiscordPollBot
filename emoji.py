EMOJI_A = "\N{REGIONAL INDICATOR SYMBOL LETTER A}"
EMOJI_Z = "\N{REGIONAL INDICATOR SYMBOL LETTER Z}"

allowed_emoji = [chr(codepoint) for codepoint in range(ord(EMOJI_A), ord(EMOJI_Z) + 1)]
