## Privacy Policy for Word Chain Bot Indently

This Privacy Policy governs the collection, use, and sharing of personal 
information by _Word Chain Bot Indently_, a Discord bot developed by 
Wrichik Basu, in association with the Indently Bot Dev Team. By using this 
bot, you agree to the terms of this Privacy Policy.

We take privacy very seriously; as developers who love to use and contribute 
to open-source software, we feel it is necessary to disclose what information 
we collect and store, and what we do with it and which third-party entities we 
share the data with, if any.

### Applicability of this privacy policy

This Privacy Policy applies exclusively to the bot deployed from the `main` 
branch by the Indently Bot Development Team. Specifically, it pertains to 
the bot with the following details:  
- **Application ID**: `1222301436054999181`  
- **Available on Discord App Discovery**: https://discord.com/discovery/applications/1222301436054999181  
- **Listed on Top.gg**: https://top.gg/bot/1222301436054999181

> **Note**: This policy does *not* extend to any instances of the bot 
hosted by third parties, including those deployed from the same repo 
or from a forked version.

### Information we collect
- When you are interacting with the bot, we collect and store your user ID, along 
with the server ID where you are playing the game. This means, if you are 
playing the game in multiple servers, we store your user ID and the 
corresponding server ID for each of those servers.
- We store how many words you have entered correctly, how many mistakes 
you have made, and statistics based on those two values.
- We store the names of the servers where our bot is being used. This is 
used to display the server leaderboard. If you are a server manager/admin 
adding the bot to your server, we assume that you have granted us 
permission to store the name of your server.

### Information we do NOT collect
- The words that you enter while playing the game are NOT linked to your user ID.
This means that it is **impossible** _for anyone to trace which word was entered by 
which user, and vice versa_. Thus, **we maintain complete anonymity** in the 
data that we store.
- The karma value is based on the words that you enter; to be specific, the 
beginning and ending letters. However, we do NOT store the words that you
enter. We calculate the karma value on the fly as soon as you enter a word, 
and store that value in the database.

### How we use the stored information
- The stored information is used in the game only.
- The Bot maintains statistics of how many correct and wrong inputs 
you have entered, your score and karma.
- We use these to determine your position on the user leaderboard. 
- On the global user leaderboard, we display your name in the format <@user_id>.
This means that your display name remains hidden if you are not a member of 
the server where the command was executed.
- If the server(s) you are playing in has set a reliable role and a failed 
role, we use the stored metrics to determine whether you qualify for any of 
these roles, and thereafter add you to these roles.
- For the server leaderboard, we use the stored names of the servers.

### Third-party entities with whom we share your data
We do NOT share any stored data with any third-party entity. Everything 
remains within our database, that can only be accessed by the bot owners.

### Data deletion on user request
We can delete your data associated with the bot. This includes your user ID, 
the corresponding servers where you have played the game, and metrics like 
score or karma. If you would like to delete your data, please reach out to 
us via `basulabs.developer@gmail.com`.

### Privileged Intents that the Bot requires, and why they are needed
The Bot requires two privileged intents:
- **Message Content Intent**  
This intent is of utmost importance and the bot will not function without it. 
We require this intent to read the words that the users send in the game 
channel, check if that word is correct (i.e. conforms to the game rules), 
and then store it in the database.
- **Server Members Intent**  
This required so that: 
  - We can fetch usernames and nicknames when showing the leaderboard of 
the server or the global leaderboard, and,
  - We can retrieve the users who have the reliable role and the failed role, 
and make sure that only the correct people have those roles.

### Permissions that the bot requires

|       Permission       | Why it is required                                                                                                                           |
|:----------------------:|----------------------------------------------------------------------------------------------------------------------------------------------|
|     `Manage Roles`     | Used to grant/remove the failed role and reliable role.                                                                                      |
| `Read Message History` | Required to detect when a user deletes a word.                                                                                               |
|    `View Channels`     | Basic permission required to view the channels and allow the server manager/admins to set the game channel.                                  |
|    `Add Reactions`     | Required to add the tick mark to a correct input, or the cross mark to an incorrect input.                                                   |
|    `Send Messages`     | Another basic permission, required to send messages (e.g. when the chain is broken or an already used word is repeated) in the game channel. |
| `Add External Emojis`  | Not exactly required at the moment, but we will bring some updates where we may introduce custom emojis that will be added as reactions.     |

### Changes to this Policy

We may update this Privacy Policy from time to time, and we will 
post the updated policy on our website. Your continued use of our bot after 
we make changes to this policy indicates your acceptance of the revised policy.

### Contact us

If you have any questions regarding our privacy practices, feel free to 
drop an email to `basulabs.developer@gmail.com`, and we shall get back to 
you as soon as possible.

That's all for now; and we thank you for using our app!

