"""Cog that contains the actual game logic."""
from __future__ import annotations

import logging
import re
from asyncio import Future
from collections import deque
from logging.config import fileConfig
from typing import TYPE_CHECKING, Optional

import discord
from discord import MessageType
from discord.ext import commands
from discord.ext.commands import Cog
from sqlalchemy import CursorResult, delete, exists, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from consts import COG_NAME_COMMON, COG_NAME_GAME, LOGGER_NAME_GAME_COG, MISTAKE_PENALTY, SETTINGS, GameMode
from karma import calculate_total_karma
from language import Language
from model import BannedMemberModel, MemberModel, ServerConfig, UsedWordsModel

if TYPE_CHECKING:
    from cogs.common import CommonCog
    from main import WordChainBot

fileConfig(fname='config.ini')
logger = logging.getLogger(LOGGER_NAME_GAME_COG)


class GameCog(Cog, name=COG_NAME_GAME):

    def __init__(self, bot: WordChainBot, common: CommonCog):
        self.bot: WordChainBot = bot
        self.common: CommonCog = common
        super().__init__()

    # ----------------------------------------------------------------------------------------------------------------

    def cog_load(self) -> None:
        logger.info(f'Cog {self.qualified_name} loaded.')

    # ----------------------------------------------------------------------------------------------------------------

    def cog_unload(self) -> None:
        logger.info('Removing commands...')

        for command in self.bot.tree.get_commands():  # Loop through all commands in the bot
            if command in self.__cog_commands__:  # And remove the ones that are in the specified cog
                self.bot.tree.remove_command(command.name)

        logger.info(f'Cog {self.qualified_name} unloaded.')

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return

        if message.author.bot:
            return

        if not message.content:
            return

        if not message.guild:
            return

        server_id = message.guild.id

        # Check if we have a config ready for this server, and the server has been marked as ready
        if server_id not in self.common.server_configs or server_id not in self.common.servers_ready:
            return

        await self.common.ensure_config(message.guild)
        config = self.common.server_configs[server_id]
        if message.channel.id == config.game_state[GameMode.NORMAL].channel_id:
            await self.on_message_for_word_chain(message, GameMode.NORMAL)
        elif message.channel.id == config.game_state[GameMode.HARD].channel_id:
            await self.on_message_for_word_chain(message, GameMode.HARD)

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Post a message in the channel if a user deletes their input."""
        if message.type != MessageType.default:
            # return early if it was not caused by a normal user message, e.g. use of commands
            return

        if not self.bot.is_ready():
            return

        if message.author == self.bot.user:
            return

        if not message.guild:
            return

        await self.common.ensure_config(message.guild)
        config = self.common.server_configs[message.guild.id]

        # Check if the message is in the channel
        if message.channel.id not in (config.game_state[GameMode.NORMAL].channel_id,
                                      config.game_state[GameMode.HARD].channel_id):
            return
        if not message.reactions:
            return
        if not any(self.common.word_matches_pattern(message.content, language.value) for language in config.languages):
            return

        if message.channel.id == config.game_state[GameMode.NORMAL].channel_id:
            if config.game_state[GameMode.NORMAL].current_word:
                await self.send_message_to_channel(message.channel, f'{message.author.mention} edited their word! '
                                                                            f'The **last** word was **{config.game_state[GameMode.NORMAL].current_word}**.')
            else:
                await self.send_message_to_channel(message.channel, f'{message.author.mention} edited their word!')
        elif message.channel.id == config.game_state[GameMode.HARD].channel_id:
            if config.game_state[GameMode.HARD].current_word:
                await self.send_message_to_channel(message.channel, f'{message.author.mention} edited their word! '
                                                                            f'The **last** word was **{config.game_state[GameMode.HARD].current_word}**.')
            else:
                await self.send_message_to_channel(message.channel, f'{message.author.mention} edited their word!')

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Send a message in the channel if a user modifies their input."""
        if before.type != MessageType.default:
            # return early if it was not caused by a normal user message, e.g. use of commands
            return


        if not self.bot.is_ready():
            return

        if before.author == self.bot.user:
            return

        if not before.guild:
            return

        await self.common.ensure_config(before.guild)
        config = self.common.server_configs[before.guild.id]

        # Check if the message is in the channel
        if before.channel.id not in (config.game_state[GameMode.NORMAL].channel_id,
                                     config.game_state[GameMode.HARD].channel_id):
            return
        if not before.reactions:
            return
        if not any(self.common.word_matches_pattern(before.content, language.value) for language in config.languages):
            return
        if before.content.lower() == after.content.lower():
            return

        if before.channel.id == config.game_state[GameMode.NORMAL].channel_id:
            if config.game_state[GameMode.NORMAL].current_word:
                await self.send_message_to_channel(after.channel, f'{after.author.mention} edited their word! '
                                                                          f'The **last** word was **{config.game_state[GameMode.NORMAL].current_word}**.')
            else:
                await self.send_message_to_channel(after.channel, f'{after.author.mention} edited their word!')
        elif before.channel.id == config.game_state[GameMode.HARD].channel_id:
            if config.game_state[GameMode.HARD].current_word:
                await self.send_message_to_channel(after.channel, f'{after.author.mention} edited their word! '
                                                                          f'The **last** word was **{config.game_state[GameMode.HARD].current_word}**.')
            else:
                await self.send_message_to_channel(after.channel, f'{after.author.mention} edited their word!')

    # ---------------------------------------------------------------------------------------------------------------

    async def on_message_for_word_chain(self, message: discord.Message, game_mode: GameMode) -> None:
        """
        Checks if the message is a valid word.

        Hierarchy of checking:
            1. Match regex pattern.
            2. Word length must be > 1.
            3. Is member banned? --> Yes => Simply ignore the input.
            4. Is word whitelisted? (Global/server-specific) --> If yes, skip to #8.
            5. Is the word blacklisted? (Global/server-specific)
            6. If the word has letters out of the English alphabet, and the server has ONLY English
               enabled, then it is an error. (We do not send the word to Wiktionary as Wiktionary English
               has lots of words outside English.)
            7. Is the word valid? (Check cache/start query if not found in cache)
            8. Repetition?
            9. Wrong member?
            10. Wrong starting letter?
        """
        if not message.guild:
            return
        server_id = message.guild.id
        # no ensure_config needed here, this is already done in the upper call frame
        config: ServerConfig = self.common.server_configs[server_id]
        word: str = message.content.lower()
        server_languages: list[Language] = config.languages
        valid_languages: list[Language] = [language for language in server_languages if self.common.word_matches_pattern(word, language.value)]

        if not valid_languages:
            if not any(c.isspace() for c in word):
                # in this case, we have a single word, that did not match any of the configured language regex patterns
                await self.add_reaction(message, '⚠️')
                await self.send_message_to_channel(message.channel, f'''Your word is not a valid word in any of your configured languages.
The chain has **not** been broken. Please enter another word.''')
            return
        if len(word) == 0:
            return

        # -------------------------------
        # Check if member is banned
        # -------------------------------
        async with self.bot.db_connection() as connection:
            stmt = select(exists(BannedMemberModel).where(
                BannedMemberModel.member_id == message.author.id
            ))
            result: CursorResult = await connection.execute(stmt)
            member_banned = result.scalar()
            if member_banned:
                return

        # --------------------
        # Check word length
        # --------------------
        if len(word) == 1:
            await self.add_reaction(message, '⚠️')
            await self.send_message_to_channel(message.channel, f'''Single-letter inputs are no longer accepted.
The chain has **not** been broken. Please enter another word.''')
            return

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # ADD USER TO THE DATABASE
        # ------------------------------------
        # We need to check whether the current user already
        # has an entry in the database. If not, we have to add an entry.
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        async with self.bot.db_connection() as connection:

            stmt = select(exists(MemberModel).where(
                MemberModel.member_id == message.author.id,
                MemberModel.server_id == message.guild.id
            ))
            result: CursorResult = await connection.execute(stmt)
            member_exists = result.scalar()

            if not member_exists:
                stmt = insert(MemberModel).values(
                    server_id=message.guild.id,
                    member_id=message.author.id,
                    score=0,
                    correct=0,
                    wrong=0,
                    karma=0.0
                )
                await connection.execute(stmt)
                await connection.commit()

        # ++++++++++++++++++++++++++ Adding user completed ++++++++++++++++++++++++++++++

        # +++++++++++++++++++++
        # CHECK THE WORD
        # +++++++++++++++++++++
        async with self.bot.db_connection() as connection:

            # -------------------------------
            # Check if word is whitelisted
            # -------------------------------
            word_whitelisted: bool = await self.common.is_word_whitelisted(word, message.guild.id, connection)

            # -----------------------------------
            # Check if word is blacklisted
            # (if and only if not whitelisted)
            # -----------------------------------
            if not word_whitelisted and await self.common.is_word_blacklisted(word, message.guild.id, connection):
                await self.add_reaction(message, '⚠️')
                await self.send_message_to_channel(message.channel, f'''This word has been **blacklisted**. Please do not use it.
The chain has **not** been broken. Please enter another word.''')
                return

            # ----------------------------------------
            # Check if word is valid
            # (if and only if not whitelisted)
            # -----------------------------------------
            futures: Optional[list[Future]]

            # First check the whitelist or the word cache
            matched_language = await self.common.is_word_in_cache(word, connection, server_languages)
            if word_whitelisted or matched_language:
                # Word found in cache. No need to query API
                futures = None
            else:
                # Word neither whitelisted, nor found in cache.
                # Start the API request, but deal with it later.
                # Query only languages where word would be valid.
                futures = self.common.start_api_queries(word, valid_languages)

            # -----------------------------------
            # Check repetitions
            # (Repetitions are not mistakes)
            # -----------------------------------
            stmt = select(exists(UsedWordsModel).where(
                UsedWordsModel.server_id == message.guild.id,
                UsedWordsModel.game_mode == game_mode.value,
                UsedWordsModel.word == word
            ))
            result: CursorResult = await connection.execute(stmt)
            word_already_used = result.scalar()
            if word_already_used:
                await self.add_reaction(message, '⚠️')
                await self.send_message_to_channel(message.channel, f'''The word *{word}* has already been used before. \
The chain has **not** been broken.
Please enter another word.''')
                return

            # -------------
            # Wrong member
            # -------------
            if not SETTINGS.single_player and config.game_state[game_mode].last_member_id == message.author.id:
                response: str = f'''{message.author.mention} messed up the count! \
*You cannot send two words in a row!*
{f'The chain length was {config.game_state[game_mode].current_count} when it was broken. :sob:\n' if config.game_state[game_mode].current_count > 0 else ''}\
Restart with a word starting with **{config.game_state[game_mode].current_word[-game_mode.value:]}** and \
try to beat the current high score of **{config.game_state[game_mode].high_score}**!'''

                await self.handle_mistake(message, response, connection, game_mode)
                await connection.commit()
                return

            # -------------------------
            # Wrong starting letter
            # -------------------------
            if (config.game_state[game_mode].current_word and word[:game_mode.value] !=
                    config.game_state[game_mode].current_word[-game_mode.value:]):

                response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered did not begin with the last letter of the previous word* (**{config.game_state[game_mode].current_word[-game_mode.value:]}**).
{f'The chain length was {config.game_state[game_mode].current_count} when it was broken. :sob:\n' if config.game_state[game_mode].current_count > 0 else ''}\
Restart with a word starting with **{config.game_state[game_mode].current_word[-game_mode.value:]}** and try to beat the \
current high score of **{config.game_state[game_mode].high_score}**!'''

                await self.handle_mistake(message, response, connection, game_mode)
                await connection.commit()
                return

            # ----------------------------------
            # Check if word is valid (contd.)
            # ----------------------------------
            query_result_code: int

            if futures:
                for future in futures:
                    query_result_code = self.common.get_query_response(future)

                    if query_result_code == self.common.API_RESPONSE_WORD_EXISTS:
                        # The word exists in at least one of the languages the server is configured for.
                        # We don't need to loop over the other Future objects.
                        response = future.result(timeout=5)
                        data = response.json()
                        lang_code: str = (data[3][0]).split('//')[1].split('.')[0]
                        queried_language: Language = Language.from_language_code(lang_code)

                        # many foreign words can be found in a languages wiktionary, we accept a word only as existing
                        # if it does match the languages word regex
                        if self.common.word_matches_pattern(word, queried_language.value):
                            matched_language: Language = queried_language
                            break

                # Add the words to the cache for all languages
                await self.common.add_words_to_cache(futures, connection)

                if query_result_code == self.common.API_RESPONSE_WORD_DOESNT_EXIST:
                    if config.game_state[game_mode].current_word:
                        response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered does not exist.^*
{f'The chain length was {config.game_state[game_mode].current_count} when it was broken. :sob:\n' if config.game_state[game_mode].current_count > 0 else ''}\
Restart with a word starting with **{config.game_state[game_mode].current_word[-game_mode.value:]}** and try to beat the \
current high score of **{config.game_state[game_mode].high_score}**!

-# ^ The bot now supports multiple languages. When a word is invalid, it pertains to the language(s) \
enabled in this server.\n-# To check enabled languages, use `/show_languages`.'''

                    else:
                        response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered does not exist.*
Restart and try to beat the current high score of **{config.game_state[game_mode].high_score}**!'''

                    await self.handle_mistake(message, response, connection, game_mode)
                    await connection.commit()
                    return

                elif query_result_code == self.common.API_RESPONSE_ERROR:
                    await self.add_reaction(message, '⚠️')
                    await self.send_message_to_channel(message.channel, ''':octagonal_sign: There was an issue in the backend.
The above entered word is **NOT** being taken into account.''')
                    return

            # --------------------
            # Check word score
            # --------------------
            if all(language.value.score_threshold[game_mode] > self.calculate_word_score(word, game_mode, language) for language in server_languages):
                await self.add_reaction(message, '⚠️')
                await self.send_message_to_channel(message.channel, f'''Your word has no or just few words to continue with.
The chain has **not** been broken. Please enter another word.\n
-# If you think this is wrong, please let us know on our support server.''')
                return

            # --------------------
            # Everything is fine
            # --------------------
            config.update_current(game_mode=game_mode,
                                  member_id=message.author.id,
                                  current_word=word)

            await self.add_reaction(message, config.reaction_emoji(game_mode))

            last_words: deque[str] = self.common.server_histories[server_id][message.author.id][game_mode]
            # fallback to first configured language if matched_language is unavailable (e.g. matched by whitelist)
            matched_language = matched_language if matched_language else server_languages[0]
            karma: float = calculate_total_karma(word, last_words, matched_language.value, game_mode)
            logger.debug(f'member {message.author.id} got {karma} karma for "{word}"')
            self.common.server_histories[server_id][message.author.id][game_mode].append(word)

            stmt = update(MemberModel).where(
                MemberModel.server_id == message.guild.id,
                MemberModel.member_id == message.author.id
            ).values(
                score=MemberModel.score + 1,
                correct=MemberModel.correct + 1,
                karma=func.max(0, MemberModel.karma + karma)
            )
            await connection.execute(stmt)

            stmt = insert(UsedWordsModel).values(
                server_id=message.guild.id,
                game_mode=game_mode.value,
                word=word
            )
            await connection.execute(stmt)

            current_count = config.game_state[game_mode].current_count

            if current_count > 0 and current_count % 100 == 0:
                await self.send_message_to_channel(message.channel, f'{current_count} words! Nice work, keep it up!')

            # Check and reset the server config.failed_member_id to None.
            if self.common.server_failed_roles[server_id] and config.failed_member_id == message.author.id:
                config.correct_inputs_by_failed_member += 1
                if config.correct_inputs_by_failed_member >= 30:
                    config.failed_member_id = None
                    config.correct_inputs_by_failed_member = 0
                    await self.common.add_remove_failed_role(message.guild, connection)

            await self.common.add_remove_reliable_role(message.guild, connection)
            await config.sync_to_db_with_connection(connection)

            await connection.commit()

    # ---------------------------------------------------------------------------------------------------------------

    async def handle_mistake(self, message: discord.Message, response: str, connection: AsyncConnection,
                             game_mode: GameMode) -> None:
        """Handles when someone messes up the count with a wrong number"""
        if not message.guild:
            return

        server_id = message.guild.id
        member_id = message.author.id
        # no ensure_config needed here, this is already done in the upper call frame
        config = self.common.server_configs[server_id]
        if self.common.server_failed_roles[server_id]:
            config.failed_member_id = member_id  # Designate current user as failed member
            await self.common.add_remove_failed_role(message.guild, connection)

        config.fail_chain(game_mode, member_id)

        await self.send_message_to_channel(message.channel, response)
        await self.add_reaction(message, '❌')

        stmt = update(MemberModel).where(
            MemberModel.server_id == server_id,
            MemberModel.member_id == member_id
        ).values(
            score=MemberModel.score - 1,
            wrong=MemberModel.wrong + 1,
            karma=func.max(0, MemberModel.karma - MISTAKE_PENALTY)
        )
        await connection.execute(stmt)

        stmt = delete(UsedWordsModel).where(
            UsedWordsModel.server_id == server_id,
            UsedWordsModel.game_mode == game_mode.value
        )
        await connection.execute(stmt)

        await config.sync_to_db_with_connection(connection)

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def add_reaction(message: discord.Message, emoji: str | discord.Emoji | discord.PartialEmoji) -> None:
        """
        Adds the reaction to the given message, with error handling for missing permissions.

        Parameters
        ----------
        message : discord.Message
            The message to add the reaction to.
        emoji : str | discord.Emoji | discord.PartialEmoji
            The emoji to add.
        """
        try:
            await message.add_reaction(emoji)
        except discord.errors.Forbidden:
            pass
        except discord.errors.NotFound:
            logger.warning("Failed to add reaction as message was not found.")

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def send_message_to_channel(channel: discord.abc.Messageable, content: str) -> None:
        """
        Sends a message to the given channel, with error handling for missing permissions.

        Parameters
        ----------
        channel : discord.TextChannel
            The channel to send the message to.
        content : str
            The content of the message.
        """
        try:
            await channel.send(content)
        except discord.errors.Forbidden:
            pass

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def calculate_word_score(word: str, game_mode: GameMode, language: Language) -> float:
        if re.match(language.value.allowed_word_regex, word):
            end_token = word[-game_mode.value:]
            return language.value.first_token_scores[game_mode][end_token]
        return 0.0

# ====================================================================================================================


async def setup(bot: WordChainBot):
    common = bot.get_cog(COG_NAME_COMMON)
    await bot.add_cog(GameCog(bot, common))
