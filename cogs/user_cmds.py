from __future__ import annotations

import logging
import os
from collections import defaultdict
from concurrent.futures import Future
from typing import TYPE_CHECKING, Optional, Sequence

import discord
from discord import Colour, Embed, Interaction, SelectOption, app_commands
from discord.ext.commands import Cog
from discord.ui import View
from dotenv import load_dotenv
from sqlalchemy import CursorResult, func, or_, select
from sqlalchemy.engine.row import Row
from sqlalchemy.sql.functions import count
from unidecode import unidecode

from cogs.manager_cmds import ManagerCommandsCog
from consts import COG_NAME_USER_CMDS, GameMode, LOGGER_NAME_USER_COG, Languages
from model import BannedMemberModel, Member, MemberModel, ServerConfig, ServerConfigModel
from views.dropdown import Dropdown

if TYPE_CHECKING:
    from main import WordChainBot

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger: logging.Logger = logging.getLogger(LOGGER_NAME_USER_COG)

load_dotenv()
ADMIN_GUILD_ID: int = int(os.environ['ADMIN_GUILD_ID'])


class UserCommandsCog(Cog, name=COG_NAME_USER_CMDS):

    def __init__(self, bot: WordChainBot) -> None:
        self.bot = bot
        self.bot.tree.add_command(UserCommandsCog.StatsCmdGroup(self))
        self.bot.tree.add_command(UserCommandsCog.LeaderboardCmdGroup(self))

    # ---------------------------------------------------------------------------------------------------------------

    def cog_load(self) -> None:
        logger.info(f'Cog {self.qualified_name} loaded.')

    # ---------------------------------------------------------------------------------------------------------------

    def cog_unload(self) -> None:

        logger.info('Removing commands...')

        for command in self.bot.tree.get_commands():  # Loop through all commands in the bot
            if command in self.__cog_commands__:  # And remove the ones that are in the specified cog
                self.bot.tree.remove_command(command.name)

        logger.info(f'Cog {self.qualified_name} unloaded.')

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='support', description='Join our support server!')
    async def support(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=self.HelpCommand.get_support_server_embed())

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='vote', description='Vote for the bot!')
    async def vote(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(embed=self.HelpCommand.get_vote_embed())

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='show_languages', description='Lists the languages enabled in this server')
    async def show_languages(self, interaction: Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        emb: Embed = Embed(colour=Colour.gold(), title='Languages enabled in this server', description='')
        emb.description = ManagerCommandsCog.LanguageCmdGroup.get_current_languages(self.bot, interaction.guild.id)

        await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='check_word', description='Check if a word is correct')
    @app_commands.describe(word='The word to check')
    async def check_word(self, interaction: Interaction, word: str):
        """
        Checks if a word is valid.

        Hierarchy followed:
        1. Legal characters.
        2. Length of word must be > 1.
        3. Whitelist.
        4. Blacklists
        5. Check word cache.
        6. Query API.
        """
        await interaction.response.defer(ephemeral=True)

        emb = Embed(color=Colour.blurple())

        if not self.bot.word_matches_pattern(word):
            emb.description = f'❌ **{word}** is **not** a legal word.'
            await interaction.followup.send(embed=emb)
            return

        if len(word) == 1:
            emb.description = f'❌ **{word}** is **not** a valid word.'
            await interaction.followup.send(embed=emb)
            return

        word = word.lower()

        async with self.bot.db_connection() as connection:
            if await self.bot.is_word_whitelisted(word, interaction.guild.id, connection):
                emb.description = f'''✅ The word **{word}** is valid.\n
-# Please note that the validity of words is checked only for the languages that are enabled in the server. \
Therefore, a word that is valid in this server may not be valid in another server.'''
                await interaction.followup.send(embed=emb)
                return

            if await self.bot.is_word_blacklisted(word, interaction.guild.id, connection):
                emb.description = f'❌ The word **{word}** is **blacklisted** and hence, **not** valid.'
                await interaction.followup.send(embed=emb)
                return

            # --------------------------------------------------------------------------------------------
            # Wiktionary English version has lots of words from other languages too. This includes
            # words that have accents as well. Therefore, we check if all the characters in the word
            # are from the English alphabet. If not, and the server is set to only English, then
            # this is an invalid word. We do not go for an API query and end the execution here.
            # --------------------------------------------------------------------------------------------
            if (unidecode(word) != word  # => Word is not in English...
                and Languages.ENGLISH in self.bot.server_configs[interaction.guild.id].languages  # ... but English is enabled in the server...
                    and len(self.bot.server_configs[interaction.guild.id].languages) == 1):  # ...AND English is the ONLY language in the server

                emb.description = f'''❌ The word **{word}** does not exist, and hence, **not** valid.
               
-# ^ The bot now supports multiple languages. When a word is invalid, it pertains to the language(s) \
enabled in this server.\n-# To check enabled languages, use `/show_languages`.'''

                await interaction.followup.send(embed=emb)
                return

            if await self.bot.is_word_in_cache(word, connection,
                                               self.bot.server_configs[interaction.guild.id].languages):
                emb.description = f'''✅ The word **{word}** is valid.\n
-# Please note that the validity of words is checked only for the languages that are enabled in the server. \
Therefore, a word that is valid in this server may not be valid in another server.'''
                await interaction.followup.send(embed=emb)
                return

            futures: list[Future] = self.bot.start_api_queries(word,
                                                               self.bot.server_configs[interaction.guild.id].languages)

            query_response_code: int

            for future in futures:
                match query_response_code := self.bot.get_query_response(future):

                    case self.bot.API_RESPONSE_WORD_EXISTS:
                        emb.description = f'''✅ The word **{word}** is valid.\n
-# Please note that the validity of words is checked only for the languages that are enabled in the server. \
Therefore, a word that is valid in this server may not be valid in another server.'''

                        await self.bot.add_words_to_cache(futures,
                                                          connection)  # Check and add to cache for all selected languages
                        break

            if query_response_code == self.bot.API_RESPONSE_WORD_DOESNT_EXIST:
                emb.description = emb.description = f'''❌ **{word}** is **NOT** a valid word.\n
-# Please note that the validity of words is checked only for the languages that are enabled in the server. \
Therefore, a word that is valid in this server may not be valid in another server.'''

            elif query_response_code == self.bot.API_RESPONSE_ERROR:
                emb.description = f'⚠️ There was an issue in fetching the result.'

            await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='help', description='Shows the help menu')
    async def help(self, interaction: Interaction) -> None:

        await interaction.response.defer(ephemeral=True, thinking=True)

        help_cmd: UserCommandsCog.HelpCommand = UserCommandsCog.HelpCommand(self.bot, interaction)
        view1: discord.ui.View = discord.ui.View().add_item(help_cmd.get_dropdown())
        embed: Embed = Embed(title='Help Menu', colour=Colour.blurple(), description=f'Please choose an option below.')

        msg: discord.Message = await interaction.followup.send(embed=embed, view=view1, wait=True)
        help_cmd.original_message_id = msg.id

    # =================================================================================================================

    class HelpCommand:

        __HOW_TO_PLAY: str = "how_to_play"
        __GAME_RULES: str = "game_rules"
        __SETUP_IN_SERVER: str = "setup_in_server"
        __KARMA_SYSTEM: str = "karma_system"
        __LIST_OF_COMMANDS: str = "list_commands"
        __PRIVACY_POLICY: str = "privacy_policy"
        __SUPPORT_SERVER: str = "support_server"
        __OTHER_INFO: str = "other_info"
        __VOTE: str = "vote"
        __MULTI_LANGUAGE: str = "multi_language"

        # ------------------------------------------------------------------------------------------------------------

        def __init__(self, bot: WordChainBot, original_interaction: Interaction, original_message_id: int = -1) -> None:
            super().__init__()
            self.bot: WordChainBot = bot
            self.original_interaction: Interaction = original_interaction
            self.original_message_id: int = original_message_id  # This has to be set later, after sending the initial message

        # ------------------------------------------------------------------------------------------------------------

        def get_dropdown(self) -> Dropdown:

            options_list: list[SelectOption] = [SelectOption(label="How to play",
                                                             value=UserCommandsCog.HelpCommand.__HOW_TO_PLAY),
                                                SelectOption(label="Game rules",
                                                             value=UserCommandsCog.HelpCommand.__GAME_RULES),
                                                SelectOption(label="Karma system",
                                                             value=UserCommandsCog.HelpCommand.__KARMA_SYSTEM),
                                                SelectOption(label="Multi-language support",
                                                             value=UserCommandsCog.HelpCommand.__MULTI_LANGUAGE),
                                                SelectOption(label="Vote for the bot!!",
                                                             value=UserCommandsCog.HelpCommand.__VOTE),
                                                SelectOption(label="List of commands",
                                                             value=UserCommandsCog.HelpCommand.__LIST_OF_COMMANDS),
                                                SelectOption(label="Set up the bot in your server",
                                                             value=UserCommandsCog.HelpCommand.__SETUP_IN_SERVER),
                                                SelectOption(label="Privacy Policy",
                                                             value=UserCommandsCog.HelpCommand.__PRIVACY_POLICY),
                                                SelectOption(label="Support server",
                                                             value=UserCommandsCog.HelpCommand.__SUPPORT_SERVER),
                                                SelectOption(label="Credits and other info",
                                                             value=UserCommandsCog.HelpCommand.__OTHER_INFO)
                                                ]

            async def dropdown_callback(dropdown: Dropdown, interaction: Interaction) -> None:

                view1: View = View().add_item(dropdown.regenerate_self())

                match dropdown.values[0]:

                    case UserCommandsCog.HelpCommand.__HOW_TO_PLAY:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.get_how_to_play_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__KARMA_SYSTEM:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.get_karma_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__GAME_RULES:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.get_game_rules_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__VOTE:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.get_vote_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__LIST_OF_COMMANDS:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=self.get_cmd_list_embed(interaction),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__PRIVACY_POLICY:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=self.get_privacy_policy_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__SUPPORT_SERVER:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=self.get_support_server_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__OTHER_INFO:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=self.get_credits_embed(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__SETUP_IN_SERVER:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.setup_in_server(),
                                                                view=view1)

                    case UserCommandsCog.HelpCommand.__MULTI_LANGUAGE:
                        await interaction.followup.edit_message(self.original_message_id,
                                                                embed=UserCommandsCog.HelpCommand.
                                                                get_multi_language_embed(),
                                                                view=view1)

            return Dropdown(dropdown_callback, options_list, original_interaction=self.original_interaction,
                            max_values=1)

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_how_to_play_embed() -> Embed:

            return Embed(title="How to play", description=f'''\
## Normal Mode
The game is pretty simple.

- Enter a word that starts with the last letter of the previous correct word.  
- If your word is correct, the bot will react with a tick mark — :white_check_mark: .  
- No characters other than the letters of the English alphabet (capital and small) and hyphen (`-`) are accepted. \
Messages with anything else will be ignored.
- You can check if a word is correct using the `/check_word` command.
- Words that have been used once cannot be used again until the chain is broken. The chain, however, will **not**
 be broken if you enter a word that has been used previously. The bot will simply ask you to enter another word.
- Entering a wrong/non-existent word will break the chain.
- Once the chain is broken, all used words will be reset.
- The chain continues even if someone messes up, in the sense that one still has to enter a word beginning with the 
last letter of the previous correct word.

That's all. Go and beat the high score in your server and top the global leaderboard!! :fire:

## Hard Mode
Hard Mode is the same as normal mode, except that the first **two letters** of a word must be the 
same as the last two letters of the previous word.
''', colour=Colour.dark_orange())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_game_rules_embed() -> Embed:

            return Embed(title="Global game rules", description=f'''\
You are **not** allowed to use any automation/botting of *any* kind under any circumstances. If you are reported, \
you will be banned from the bot for a lifetime.

***Please note:** In addition to these rules, the server where you are playing may \
have other rules that are not covered here. Please check with the server moderators or administrators.*
''', colour=Colour.red())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_multi_language_embed() -> Embed:

            return Embed(title="Multi-language support", description=f'''\
The bot now allows you to enable upto two languages in a server.

The following languages are supported:
{', '.join(f'{language.name.capitalize()}' for language in Languages)}

In order to enable/disable languages, server managers can use the commands under the `/language` category.
''', colour=Colour.dark_orange())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def setup_in_server() -> Embed:

            return Embed(description=f'''\
## Basic setup
1. Add the bot to your server. You can click on the bot's profile picture and click "Add App".
2. Run `/set channel` to set the channel where the game will be played. (You need to have at least `Manage\
Server` permission to run this command.)

This will be enough to let users play the game in your server. Send any word to start the chain.

## Highly recommended setup
- Disable the `Add reactions` permissions for `@everyone` in the game channel.
> **Why do we recommend this?**
> We have seen people put check mark reactions to words that are wrong when the bot lags in putting a reaction \
(eg. when the discord API is slow due to any reason or when the bot is going through \
a restart), and thereby mislead users on what the last correct word is.

## Optional setup
1. Set the failed role using `/set failed_role`, and the reliable role with `/set reliable_role`.
2. To make sure that people have read the game rules, create a channel with the game rules, along with a \
reaction role giving access to the game channel. This will make sure that people will be able to play \
only after agreeing that they have read the rules.

For multi-language setup, see the `Multi-language support` section in the `/help` command.''', colour=Colour.yellow())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_karma_embed() -> Embed:
            return Embed(title='The Karma System', description=f'''\
The karma system is based upon the frequency of characters as the first letter of english words.

**You *gain* karma if:**
- your word starts with a letter that is less frequent than average (because it is harder to find)
- your word ends with a letter that is more frequent than average (because it makes it easier for the next player)
- you use a variety of words that end in different letters

**You *lose* karma if:**
- your word ends with a letter  (eg. `y`) that is less frequent than average (because it makes it harder \
for the next player)
- you keep using words that end in the same letter.

**You do *not* lose karma if:**
- your word starts with a letter that is more frequent than average (because you cannot choose the first letter)
**If you mess up:** You lose 5 karma points.

:point_right:  Karma will never be < 0.
:point_right:  Check your karma in the `/stats user` command.
:point_right:  To view the karma leaderboard, use `/leaderboard type:karma`.
:point_right:  To receive the <@&1305965430351073342> role, you must have karma > 50 and accuracy > 99%.\
''', colour=Colour.green())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_support_server_embed() -> Embed:
            return Embed(title='Support Server', description=f'''\
For any questions, suggestions or bug reports, or if you just want to hang out with a cool community of word chain\
players, feel free to join our support server:

https://discord.gg/yhbzVGBNw3''', colour=Colour.pink())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_cmd_list_embed(interaction: Interaction) -> Embed:

            emb = Embed(title='Slash Commands', color=Colour.blue(),
                        description='''\
`/stats user` - Shows the stats of a specific user.
`/stats server` - Shows the stats of the current server.
`/check_word` - Check if a word exists/check the spelling.
`/leaderboard` - Shows the leaderboard of the server.
`/list_commands` - Lists all the slash commands.
`/show_languages` - Lists all the supported and currently enabled languages.''')

            if interaction.user.guild_permissions.manage_guild:
                emb.description += '''\n
**Restricted commands — Server Managers only**
`/set channel` - Sets the channel to chain words.
`/set failed_role` - Sets the role to give when a user fails.
`/set reliable_role` - Sets the reliable role.

`/language show_all` - Shows all supported languages and their codes.
`/language add` - Enable a language for this server. You can add up to two languages at a time.
`/language remove` - Removes a language from the list of enabled languages.

`/unset channel` - Unsets the channel to chain words.
`/unset failed_role` - Unsets the role to give when a user fails.
`/unset reliable_role` - Unset the reliable role.

`/blacklist add` - Add a word to the blacklist for this server.
`/blacklist remove` - Remove a word from the blacklist of this server.
`/blacklist show` - Show the blacklisted words for this server.

`/whitelist add` - Add a word to the whitelist for this server.
`/whitelist remove` - Remove a word from the whitelist of this server.
`/whitelist show` - Show the whitelist words for this server.'''

            if interaction.user.guild_permissions.administrator and interaction.guild.id == ADMIN_GUILD_ID:
                emb.description += '''\n
**Restricted commands — Bot Admins only**
`/reload` - Reload a specific Cog (or all Cogs).
`/purge_data server` - Remove all data associated with a server.
`/purge_data user` - Remove all data associated with a user.
`/logging status` - Shows the status of the loggers.
`/logging enable_all` - Enables the loggers.
`/logging disable_all` - Disables the loggers.
`/logging enable_logger` - Enables a specific logger.
`/logging disable_logger` - Disables a specific logger.
`/logging set_level` - Sets the log level of a specific logger/all loggers.
`/logging test` - Tests a specific logger.'''

            return emb

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_privacy_policy_embed() -> Embed:

            return Embed(title='Privacy Policy', description=f'''\
The privacy policy is available \
[here](https://github.com/WrichikBasu/word_chain_bot_indently/blob/main/PRIVACY_POLICY.md).''',
                         color=Colour.yellow())

        # -------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_credits_embed() -> Embed:

            return Embed(title='Credits', description='''\
- **Source code**
The bot is open-source, released under the BSD-3-Clause-License. The source code is \
[available on GitHub](https://github.com/WrichikBasu/word_chain_bot_indently).
- **Hosting information**
The bot is currently hosted on Azure, courtesy of <@329857455423225856>.
- **Credits**
  - Base code taken from [Counting Bot Indently](https://github.com/guanciottaman/counting_bot_indently).
  - Base code modified for the Word Chain Bot by <@1024746441798856717>.
  - Karma system and multi-server support completely designed by <@329857455423225856>.
  - Multi-language support by <@1024746441798856717>, with inputs from <@329857455423225856>.
- **What/who is "Indently"?**
This bot was created for the [Indently Discord server](https://discord.com/invite/indently-1040343818274340935), \
and is owned by the Indently Bot Dev Team. Federico, the founder of Indently, has kindly allowed us to keep the \
name of his company in our bot's name. (btw, if you are keen to learn python and interact with fellow programmers, \
check out the Indently Discord linked above!)''', colour=Colour.teal())

        # ------------------------------------------------------------------------------------------------------------

        @staticmethod
        def get_vote_embed() -> Embed:

            return Embed(title='Vote for the bot!', description=f'''\
**Word Chain Bot Indently** is an open-source bot. We developers do not earn anything from it, but it \
is your excitement that fuels us to continue working on it. We will really appreciate it if you vote for our bot, \
as it will allow more people discover it!

[Vote on Top.gg!](https://top.gg/bot/1222301436054999181/vote)
[Vote on discordbotlist.com!](https://discordbotlist.com/bots/word-chain-bot-indently/upvote)''',
                         color=Colour.red())

    # ===================================================================================================================

    class LeaderboardCmdGroup(app_commands.Group):

        def __init__(self, parent_cog: UserCommandsCog):
            super().__init__(name='leaderboard')
            self.cog: UserCommandsCog = parent_cog

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='Shows the first 10 users with the highest score/karma')
        @app_commands.describe(metric='Use either score or karma for ordering the leaderboard')
        @app_commands.choices(metric=[
            app_commands.Choice(name='score', value='score'),
            app_commands.Choice(name='karma', value='karma')
        ])
        @app_commands.describe(
            scope='Use either users from the current server or all users globally for the leaderboard')
        @app_commands.choices(scope=[
            app_commands.Choice(name='server', value='server'),
            app_commands.Choice(name='global', value='global')
        ])
        async def user(self, interaction: Interaction, metric: Optional[app_commands.Choice[str]],
                       scope: Optional[app_commands.Choice[str]]):
            """Command to show the top 10 users with the highest score/karma."""
            await interaction.response.defer()

            board_metric: str = 'score' if metric is None else metric.value
            board_scope: str = 'server' if scope is None else scope.value

            emb = Embed(
                title=f'Top 10 users by {board_metric}',
                color=Colour.blue(),
                description=''
            )

            match board_scope:
                case 'server':
                    emb.set_author(name=interaction.guild.name,
                                   icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
                case 'global':
                    emb.set_author(name='Global')

            async with self.cog.bot.db_connection(locked=False) as connection:
                limit = 10

                match board_metric:
                    case 'score':
                        field = MemberModel.score
                    case 'karma':
                        field = MemberModel.karma
                    case _:
                        raise ValueError(f'Unknown metric {board_metric}')

                match board_scope:
                    case 'server':
                        stmt = (select(MemberModel.member_id, field)
                                .where(MemberModel.server_id == interaction.guild.id)
                                .where(~MemberModel.member_id.in_(select(BannedMemberModel.member_id)))
                                .where(field > 0)
                                .order_by(field.desc())
                                .limit(limit))
                    case 'global':
                        stmt = (select(MemberModel.member_id, func.sum(field))
                                .group_by(MemberModel.member_id)
                                .where(~MemberModel.member_id.in_(select(BannedMemberModel.member_id)))
                                .where(field > 0)
                                .order_by(func.sum(field).desc())
                                .limit(limit))
                    case _:
                        raise ValueError(f'Unknown scope {board_scope}')

                result: CursorResult = await connection.execute(stmt)
                data: Sequence[Row[tuple[int, int | float]]] = result.fetchall()

                if len(data) == 0:  # Stop when no users could be retrieved.
                    match board_scope:
                        case 'server':
                            emb.description = ':warning: No users have played in this server yet!'
                        case 'global':
                            emb.description = ':warning: No users have played yet!'
                else:
                    for i, user_data in enumerate(data, 1):
                        member_id, score_or_karma = user_data
                        match board_metric:
                            case 'score':
                                emb.description += f'{i}. <@{member_id}> **{score_or_karma}**\n'
                            case 'karma':
                                emb.description += f'{i}. <@{member_id}> **{score_or_karma:.2f}**\n'

                await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='Shows the first 10 servers with the highest highscore')
        async def server(self, interaction: Interaction, game_mode: GameMode = GameMode.NORMAL):
            """Command to show the top 10 servers with the highest highscore"""
            await interaction.response.defer()

            async with self.cog.bot.db_connection(locked=False) as connection:
                limit = 10

                match game_mode:
                    case GameMode.NORMAL:
                        stmt = (select(ServerConfigModel.server_id, ServerConfigModel.high_score)
                                .where(
                            or_(ServerConfigModel.is_banned == 0, ServerConfigModel.server_id == interaction.guild.id))
                                .where(ServerConfigModel.high_score > 0)
                                .order_by(ServerConfigModel.high_score.desc())
                                .limit(limit))
                        game_mode_name = 'Normal Mode'
                    case GameMode.HARD:
                        stmt = (select(ServerConfigModel.server_id, ServerConfigModel.hard_mode_high_score)
                                .where(
                            or_(ServerConfigModel.is_banned == 0, ServerConfigModel.server_id == interaction.guild.id))
                                .where(ServerConfigModel.high_score > 0)
                                .order_by(ServerConfigModel.hard_mode_high_score.desc())
                                .limit(limit))
                        game_mode_name = 'Hard Mode'

                emb = Embed(
                    title=f'Top 10 servers by highscore',
                    color=Colour.blue(),
                    description=''
                ).set_author(name=f'Global ({game_mode_name})')

                result: CursorResult = await connection.execute(stmt)
                data: Sequence[Row[tuple[int, int]]] = result.fetchall()

                guild_names = defaultdict(lambda: 'unknown', {g.id: g.name for g in self.cog.bot.guilds})
                for i, server_data in enumerate(data, 1):
                    server_id, high_score = server_data
                    emb.description += f'{i}. {guild_names[server_id]} **{high_score}**\n'

                await interaction.followup.send(embed=emb)

    # ===================================================================================================================

    class StatsCmdGroup(app_commands.Group):

        def __init__(self, parent_cog: UserCommandsCog):
            super().__init__(name='stats')
            self.cog: UserCommandsCog = parent_cog

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='Show the server stats for the word chain game')
        async def server(self, interaction: Interaction, game_mode: GameMode = GameMode.NORMAL) -> None:
            """Command to show the stats of the server"""
            await interaction.response.defer()

            config: ServerConfig = self.cog.bot.server_configs[interaction.guild.id]

            if config.game_state[game_mode].channel_id is None:  # channel not set yet
                await interaction.followup.send("Word Chain channel not set yet!")
                return

            server_stats_embed = Embed(
                description=f'''Game Mode: {'Normal' if game_mode == GameMode.NORMAL else 'Hard'}
Current Chain Length: {config.game_state[game_mode].current_count}
Longest chain length: {config.game_state[game_mode].high_score}
{f"**Last word:** {config.game_state[game_mode].current_word}" if config.game_state[game_mode].current_word else ""}
{f"Last word by: <@{config.game_state[game_mode].last_member_id}>" if config.game_state[game_mode].last_member_id else ""}''',
                colour=Colour.blurple()
            )
            server_stats_embed.set_author(name=interaction.guild,
                                          icon_url=interaction.guild.icon if interaction.guild.icon else None)

            await interaction.followup.send(embed=server_stats_embed)

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='Show the user stats for the word chain game')
        @app_commands.describe(member="The user whose stats you want to see")
        async def user(self, interaction: Interaction, member: Optional[discord.Member]) -> None:
            """Command to show the stats of a specific user"""
            await interaction.response.defer()

            if member is None:
                member = interaction.user

            def get_member_avatar() -> Optional[discord.Asset]:
                if member.avatar:
                    return member.avatar
                elif member.display_avatar:
                    return member.display_avatar
                else:
                    return None

            async with self.cog.bot.db_connection(locked=False) as connection:
                stmt = select(MemberModel).where(
                    MemberModel.server_id == member.guild.id,
                    MemberModel.member_id == member.id
                )
                result: CursorResult = await connection.execute(stmt)
                row = result.fetchone()

                if row is None:
                    await interaction.followup.send('You have never played in this server!')
                    return

                db_member = Member.model_validate(row)

                stmt = select(count(MemberModel.member_id)).where(
                    MemberModel.server_id == member.guild.id,
                    MemberModel.score >= db_member.score
                )
                result: CursorResult = await connection.execute(stmt)
                pos_by_score = result.scalar()

                stmt = select(count(MemberModel.member_id)).where(
                    MemberModel.server_id == member.guild.id,
                    MemberModel.karma >= db_member.karma
                )
                result: CursorResult = await connection.execute(stmt)
                pos_by_karma = result.scalar()

                emb = discord.Embed(
                    color=discord.Color.blue(),
                    description=f'''**Score:** {db_member.score} (#{pos_by_score})
**🌟Karma:** {db_member.karma:.2f} (#{pos_by_karma})
**✅Correct:** {db_member.correct}
**❌Wrong:** {db_member.wrong}
**Accuracy:** {(db_member.correct / (db_member.correct + db_member.wrong)):.2%}'''
                ).set_author(name=f"{member} | stats", icon_url=get_member_avatar())

                await interaction.followup.send(embed=emb)


# ===================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(UserCommandsCog(bot))
