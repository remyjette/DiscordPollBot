A Discord bot for making polls

Other people in chat can add their own options to the poll with `/addoption`

Add this bot to your own server at https://discord.com/oauth2/authorize?client_id=777003643060748339&scope=bot+applications.commands&permissions=91200

Or, deploy your own instance! This bot expects a bot token to be supplied as environment variable named `DISCORD_TOKEN`.
For more information on creating a bot, see Step 1 in https://discord.com/developers/docs/getting-started.

This repo also provides a Docker image to make running it easy! Example run command:
```sh
docker run --detach --name discord-poll-bot --env=DISCORD_TOKEN=<token> ghcr.io/remyjette/discord-poll-bot:latest
```
