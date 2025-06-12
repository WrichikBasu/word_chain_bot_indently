# Word Chain Bot Indently
*A word chain game bot that originated from the Indently Discord server!*

### 🥳 🎊 Announcement: This bot is now PUBLIC and can be added to any server! 🥳 🎊

Add the bot via this link: https://discord.com/oauth2/authorize?client_id=1222301436054999181

#### Where is the public version of the bot hosted?
The bot instance used in the Indently server is hosted on [bot-hosting.net](https://bot-hosting.net/?aff=1024746441798856717).
The free node they offer at zero cost works excellent compared to free nodes offered by other hosts. 
A premium node can also be purchased at a very cheap rate, which is what we use.

### Support Server
For questions, support, suggestions or to just play the game and hang out with some cool people, you are welcome to join our support server: https://discord.gg/yhbzVGBNw3

### What is the word chain game?
It's a simple game where you have to enter a word that starts with the last letter of the previous word. You cannot enter two words in a row, so this is a multi-player game. The aim is to make the chain as long as possible. Entering a wrong word or a word with a typo breaks the chain, and you start from square one again.

### Required environment variables
To host the bot yourself, you will need to set the following environment variables in `.env`:
- `TOKEN="xyz"` : You will get this from the [Discord Developers](https://discord.com/developers/) website under the `Bot` section after creating a new application.
- `ADMIN_GUILD_ID="1234"` : The ID of the server that you want to designate as the admin guild, where admin commands like `/prune` can be run.
- `DEV_MODE="True"` or `"False"` : Optional flag to prevent the bot from automatically syncing the slash commands every time it restarts. Set it to `True` if you are testing the bot, and sync manually via the `/sync` command. Can be removed in the production version.

Or maybe just use the public version to keep things simple, unless you are developing with the intention of contributing to the codebase.

### Credits
- Base code for `main.py` taken from the repo [Counting Bot for Indently](https://github.com/guanciottaman/counting_bot_indently).
Thanks to [@guanciottaman](https://github.com/guanciottaman) for making the codebase available under the MIT License!
- Base code edited for the word chain game by me, Wrichik.
- Karma system and multi-server support designed and coded by [@SirLefti](https://github.com/SirLefti).
- Basic idea of the word chain game and the use of Wiktionary API is inspired by the (now discontinued) bot [Literally](https://github.com/mettlex/literally-discord-bot).

### Who or what is `Indently`?
This bot was created for the [Indently Discord server](https://discord.com/invite/indently-1040343818274340935), and is owned by the Indently Bot Dev Team. Federico, the founder of [Indently](https://indently.io), has kindly allowed us to keep the name of his company in our bot's name. (By the way, if you are keen to learn python and interact with fellow programmers, check out the Indently Discord linked above!)
