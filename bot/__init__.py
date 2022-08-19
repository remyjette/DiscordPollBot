import discord

TEST_GUILD = discord.Object(714999738318979163)
TEST_USER = discord.Object(777347007664750592)

required_permissions = discord.Permissions(
    read_messages=True,  # To join channels so we can find the most recent poll on /addoption or /removeoption
    manage_messages=True,  # To clear invalid reacts from users and delete command messages after they are processed
    embed_links=True,  # Creating a poll doesn't need this, but *editing* the embed for /addoption & /removeoption does
    read_message_history=True,  # To find the most recent poll when a user does /addoption or /removeoption
    add_reactions=True,  # To add the initial reactions for users to be able to click on to vote
    # connect=True,  # read_messages but for Voice Chat channels. Not requiring for now, will check on command instead.
)
