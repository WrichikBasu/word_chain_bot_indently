## Word Chain Bot Indently: Privacy Policy

This Privacy Policy governs the collection, use, and sharing of personal information by _Word Chain Bot Indently_, a Discord bot developed by Wrichik Basu, in association with the Indently Bot Dev Team. By using this bot, you agree to the terms of this Privacy Policy.

We take privacy very seriously; as developers who love to use and contribute to open-source software, we feel it is necessary to disclose what information we collect, store and share with third-party entities.

### Applicability of this privacy policy
This privacy policy is applicable for the bot that is hosted from the `main` branch, by the Indently Bot Dev Team. To be specific, it applies to the bot with the application ID `1222301436054999181`. Any bots hosted by others, whether from the same branch or a fork, is not covered under this privacy policy.

### Information we collect
- When you are using the bot, we collect and store your user ID, along with the server ID where you are playing the game. This means, if you are playing the game in multiple servers, we store your user ID and the corresponding server ID for each of those servers.
- In addition, we also store how many words you have entered correctly, how many mistakes you have made, and statistics based on those two values.

### Information we do NOT collect
We do **not** collect any information on the words you have entered on any server such that you can be traced back from the word in the database. We maintain a mapping for each server so that the bot can track which words have already been used, but that mapping does **not** contain any information about who entered the word. If you are the person who entered the last word, we store your user ID and the corresponding word in the configuration, but that is only to keep track of who the last user was and what the current word is. As soon as someone else enters another word, that information is erased. Therefore, it is safe to say that there is no way to determine from the Bot's database that you sent a particular word.

### How we use the stored information
The stored information is only used in the game. The Bot maintains statistics of how many correct and wrong inputs you have entered. And we use that to determine the score and karma, and display a leaderboard. That's pretty much it.

### Third-party entities with whom we share your data
We do NOT share any stored data with any third-party entity. Everything remains within our database, that can only be accessed by the bot owners and the admin of the host where we have hosted our bot.

### Data deletion on user request
We can delete your data associated with the bot. This includes your user ID, the corresponding servers where you have played the game, and metrics like score or karma. If you would like to delete your data, please reach out to us via `basulabs.developer@gmail.com`.

### Privileged Intents that the Bot requires, and why they are needed
The Bot requires two privileged intents:
- **Message Content Intent**
This intent is of utmost importance and the bot will not function without it. We require this intent to read the words that the users send in the game channel, check if that word is correct (i.e. conforms to the game rules), and then store it in the database.
- **Server Members Intent**
This required so that we can fetch usernames and nicknames when showing the leaderboard of the server or the global leaderboard.

### Permissions that the bot requires

| Permission | Why it is required |
| :---: | --- |
| `Manage Roles` | Used to grant/remove the failed role and reliable role. |
| `Read Message History` | Required to detect when a user deletes a word. |
| `View Channels` | Basic permission required to view the channels and allow the server manager/admins to set the game channel. |
| `Add Reactions` | Required to add the tick mark to a correct input, or the cross mark to an incorrect input. |
| `Send Messages` | Another basic permission, required to send messages (e.g. when the chain is broken or an already used word is repeated) in the game channel. |
| `Add External Emojis` | Not exactly required at the moment, but we will bring some updates where we may introduce custom emojis that will be added as reactions. |

### Changes to this Policy

We may update this Privacy Policy from time to time, and we will post the updated policy on our website. Your continued use of our bot after we make changes to this policy indicates your acceptance of the revised policy.

### Contact us

If you have any questions regarding our privacy practices, feel free to drop an email to `basulabs.developer@gmail.com`, and we shall get back to you as soon as possible.

That's all for now; and we thank you for using our app!

