"""Word chain bot for the Indently server"""
import asyncio
import concurrent.futures
import contextlib
import logging
import os
import time
from collections import defaultdict, deque
from typing import AsyncIterator, Optional, Sequence

import discord
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from requests_futures.sessions import FuturesSession
from sqlalchemy import CursorResult, delete, exists, func, insert, select, update
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.sql.functions import count

from consts import *
from utils import calculate_total_karma
from model import (BlacklistModel, Member, MemberModel, ServerConfig, ServerConfigModel, UsedWordsModel, WhitelistModel,
                   WordCacheModel)

load_dotenv('.env')
# running in single player mode changes some game rules - you can chain words alone now
# getenv reads always strings, which are truthy if not empty - thus checking for common false-ish tokens
SINGLE_PLAYER = os.getenv('SINGLE_PLAYER', False) not in {False, 'False', 'false', '0'}
DEV_MODE = os.getenv('DEV_MODE', False) not in {False, 'False', 'false', '0'}
ADMIN_GUILD_ID = int(os.environ['ADMIN_GUILD_ID'])

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)


class Bot(commands.AutoShardedBot):
    """Word chain bot for Indently discord server."""

    __SQL_ENGINE = create_async_engine('sqlite+aiosqlite:///database_word_chain.sqlite3')
    __LOCK = asyncio.Lock()

    API_RESPONSE_WORD_EXISTS: int = 1
    API_RESPONSE_WORD_DOESNT_EXIST: int = 0
    API_RESPONSE_ERROR: int = -1

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.server_configs: dict[int, ServerConfig] = dict()
        self.server_failed_roles: dict[int, Optional[discord.Role]] = defaultdict(lambda: None)
        self.server_reliable_roles: dict[int, Optional[discord.Role]] = defaultdict(lambda: None)

        self._server_histories: dict[int, dict[int, deque[str]]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=HISTORY_LENGTH)))
        super().__init__(command_prefix='!', intents=intents)

    @contextlib.asynccontextmanager
    async def db_connection(self, locked=True) -> AsyncIterator[AsyncConnection]:
        logger.debug(f'requesting connection with {locked=}')
        if locked:
            start_time = time.monotonic()
            async with self.__LOCK:
                wait_time = time.monotonic() - start_time
                logger.debug(f'Waited {wait_time:.4f} seconds for DB lock')
                async with self.__SQL_ENGINE.begin() as connection:
                    yield connection
        else:
            async with self.__SQL_ENGINE.begin() as connection:
                yield connection
        logger.debug(f'connection done')

    # ---------------------------------------------------------------------------------------------------------------

    async def on_ready(self) -> None:
        """Override the on_ready method"""
        logger.info(f'Bot is ready as {self.user.name}#{self.user.discriminator}')

        # load all configs and make sure each guild has one entry
        async with self.db_connection() as connection:
            stmt = select(ServerConfigModel)
            result: CursorResult = await connection.execute(stmt)
            configs = [ServerConfig.model_validate(row) for row in result]
            self.server_configs = {config.server_id: config for config in configs}

            db_servers = {config.server_id for config in configs}
            current_servers = {guild.id for guild in self.guilds}

            servers_without_config = current_servers - db_servers  # those that do not have a config in the db

            for server_id in servers_without_config:
                new_config = ServerConfig(server_id=server_id)
                stmt = insert(ServerConfigModel).values(**new_config.model_dump())
                await connection.execute(stmt)
                logger.debug(f'created config for {server_id} in db')
                self.server_configs[server_id] = new_config

            await connection.commit()

        for guild in self.guilds:
            config = self.server_configs[guild.id]

            channel: Optional[discord.TextChannel] = bot.get_channel(config.channel_id)
            if channel:

                emb: discord.Embed = discord.Embed(description='**I\'m now online!**',
                                                   colour=discord.Color.brand_green())

                if config.high_score > 0:
                    emb.description += f'\n\n:fire: Let\'s beat the high score of {config.high_score}! :fire:\n'

                if config.current_word:
                    emb.add_field(name='Last valid word', value=f'{config.current_word}', inline=True)

                    if config.last_member_id:

                        member: Optional[discord.Member] = channel.guild.get_member(config.last_member_id)
                        if member:
                            emb.add_field(name='Last input by', value=f'{member.mention}', inline=True)

                await channel.send(embed=emb)
                self.load_discord_roles(guild)
        logger.info(f'Loaded {len(self.server_configs)} server configs, running on {len(self.guilds)} servers')

    # ---------------------------------------------------------------------------------------------------------------

    async def on_guild_join(self, guild: discord.Guild):
        """Override the on_guild_join method"""
        logger.info(f'Joined guild {guild.name} ({guild.id})')

        async with self.db_connection() as connection:
            new_config = ServerConfig(server_id=guild.id)
            stmt = insert(ServerConfigModel).values(**new_config.model_dump()).prefix_with('OR IGNORE')
            await connection.execute(stmt)
            await connection.commit()
            self.server_configs[new_config.server_id] = new_config

    # ---------------------------------------------------------------------------------------------------------------

    def load_discord_roles(self, guild: discord.Guild):
        """
        Sets the `self.server_failed_roles` and `self.server_reliable_roles` variables.
        """
        config = self.server_configs[guild.id]
        if config.failed_role_id is not None:
            self.server_failed_roles[guild.id] = discord.utils.get(guild.roles, id=config.failed_role_id)
        else:
            self.server_failed_roles[guild.id] = None

        if config.reliable_role_id is not None:
            self.server_reliable_roles[guild.id] = discord.utils.get(guild.roles, id=config.reliable_role_id)
        else:
            self.server_reliable_roles[guild.id] = None

    # ---------------------------------------------------------------------------------------------------------------

    async def add_remove_reliable_role(self, guild: discord.Guild, connection: AsyncConnection):
        """
        Adds/removes the reliable role if present to make sure it matches the rules.

        Criteria for getting the reliable role:
        1. Accuracy must be >= `RELIABLE_ROLE_ACCURACY_THRESHOLD`. (Accuracy = correct / (correct + wrong))
        2. Karma must be >= `RELIABLE_ROLE_KARMA_THRESHOLD`
        """
        if self.server_reliable_roles[guild.id]:
            stmt = select(MemberModel.member_id).where(
                MemberModel.server_id == guild.id,
                MemberModel.member_id.in_([member.id for member in guild.members]),
                MemberModel.karma > RELIABLE_ROLE_KARMA_THRESHOLD,
                (MemberModel.correct / (MemberModel.correct + MemberModel.wrong)) > RELIABLE_ROLE_ACCURACY_THRESHOLD
            )
            result: CursorResult = await connection.execute(stmt)
            db_members: set[int] = {row[0] for row in result}
            role_members: set[int] = {member.id for member in self.server_reliable_roles[guild.id].members}

            only_db_members = db_members - role_members  # those that should have the role but do not
            only_role_members = role_members - db_members  # those that have the role but should not

            for member_id in only_db_members:
                member: Optional[discord.Member] = guild.get_member(member_id)
                if member:
                    await member.add_roles(self.server_reliable_roles[guild.id])

            for member_id in only_role_members:
                member: Optional[discord.Member] = guild.get_member(member_id)
                if member:
                    await member.remove_roles(self.server_reliable_roles[guild.id])

    # ---------------------------------------------------------------------------------------------------------------

    async def add_remove_failed_role(self, guild: discord.Guild, connection: AsyncConnection):
        """
        Adds the `failed_role` to the user whose id is stored in `failed_member_id`.
        Removes the failed role from all other users.
        Does not proceed if failed role has not been set.
        If `failed_role` is not `None` but `failed_member_id` is `None`, then simply removes
        the failed role from all members who have it currently.
        """
        if self.server_failed_roles[guild.id]:
            handled_member = False
            for member in self.server_failed_roles[guild.id].members:
                if self.server_configs[guild.id].failed_member_id == member.id:
                    # Current failed member already has the failed role, so just continue
                    handled_member = True
                    continue
                else:
                    # Either failed_member_id is None, or this member is not the current failed member.
                    # In either case, we have to remove the role.
                    await member.remove_roles(self.server_failed_roles[guild.id])

            if not handled_member and self.server_configs[guild.id].failed_member_id:
                # Current failed member does not yet have the failed role
                try:
                    failed_member: discord.Member = await guild.fetch_member(
                        self.server_configs[guild.id].failed_member_id)
                    await failed_member.add_roles(self.server_failed_roles[guild.id])
                except discord.NotFound:
                    # Member is no longer in the server
                    self.server_configs[guild.id].failed_member_id = None
                    self.server_configs[guild.id].correct_inputs_by_failed_member = 0
                    await self.server_configs[guild.id].sync_to_db_with_connection(connection)

    # ---------------------------------------------------------------------------------------------------------------

    async def on_message(self, message: discord.Message) -> None:
        """
        Hierarchy of checking:
        1. Word length must be > 1.
        2. Is word whitelisted? --> If yes, skip to #5.
        3. Is the word blacklisted?
        4. Is the word valid? (Check cache/start query if not found in cache)
        5. Repetition?
        6. Wrong member?
        7. Wrong starting letter?
        """

        if message.author == self.user:
            return

        server_id = message.guild.id

        # Check if we have a config ready for this server
        if server_id not in self.server_configs:
            return

        # Check if the message is in the channel
        if message.channel.id != self.server_configs[server_id].channel_id:
            return

        word: str = message.content.lower()

        if not all(c in POSSIBLE_CHARACTERS for c in word):
            return
        if len(word) == 0:
            return

        # --------------------
        # Check word length
        # --------------------
        if len(word) == 1:
            await message.add_reaction('⚠️')
            await message.channel.send(f'''Single-letter inputs are no longer accepted.
The chain has **not** been broken. Please enter another word.''')
            return

        async with self.db_connection() as connection:
            # ----------------------------------------------------------------------------------------
            # ADD USER TO THE DATABASE
            # ----------------------------------------------------------------------------------------
            # We need to check whether the current user already has an entry in the database.
            # If not, we have to add an entry.
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

        async with self.db_connection() as connection:
            # -------------------------------
            # Check if word is whitelisted
            # -------------------------------
            word_whitelisted: bool = await self.is_word_whitelisted(word, message.guild.id, connection)

            # -------------------------------
            # Check if word is blacklisted
            # (iff not whitelisted)
            # -------------------------------
            if not word_whitelisted and await self.is_word_blacklisted(word, message.guild.id, connection):
                await message.add_reaction('⚠️')
                await message.channel.send(f'''This word has been **blacklisted**. Please do not use it.
The chain has **not** been broken. Please enter another word.''')
                return

            # ------------------------------
            # Check if word is valid
            # (if and only if not whitelisted)
            # ------------------------------
            future: Optional[concurrent.futures.Future]

            # First check the whitelist or the word cache
            if word_whitelisted or await self.is_word_in_cache(word, connection):
                # Word found in cache. No need to query API
                future = None
            else:
                # Word neither whitelisted, nor found in cache.
                # Start the API request, but deal with it later
                future = self.start_api_query(word)

            # -----------------------------------
            # Check repetitions
            # (Repetitions are not mistakes)
            # -----------------------------------
            stmt = select(exists(UsedWordsModel).where(
                UsedWordsModel.server_id == message.guild.id,
                UsedWordsModel.word == word
            ))
            result: CursorResult = await connection.execute(stmt)
            word_already_used = result.scalar()
            if word_already_used:
                await message.add_reaction('⚠️')
                await message.channel.send(f'''The word *{word}* has already been used before. \
The chain has **not** been broken.
Please enter another word.''')
                return

            # -------------
            # Wrong member
            # -------------
            if not SINGLE_PLAYER and self.server_configs[server_id].last_member_id == message.author.id:
                response: str = f'''{message.author.mention} messed up the count! \
*You cannot send two words in a row!*
{f'The chain length was {self.server_configs[server_id].current_count} when it was broken. :sob:\n' if self.server_configs[server_id].current_count > 0 else ''}\
Restart with a word starting with **{self.server_configs[server_id].current_word[-1]}** and \
try to beat the current high score of **{self.server_configs[server_id].high_score}**!'''

                await self.handle_mistake(message, response, connection)
                await connection.commit()
                return

            # -------------------------
            # Wrong starting letter
            # -------------------------
            if self.server_configs[server_id].current_word and word[0] != self.server_configs[server_id].current_word[
                -1]:
                response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered did not begin with the last letter of the previous word* (**{self.server_configs[server_id].current_word[-1]}**).
{f'The chain length was {self.server_configs[server_id].current_count} when it was broken. :sob:\n' if self.server_configs[server_id].current_count > 0 else ''}\
Restart with a word starting with **{self.server_configs[server_id].current_word[-1]}** and try to beat the \
current high score of **{self.server_configs[server_id].high_score}**!'''

                await self.handle_mistake(message, response, connection)
                await connection.commit()
                return

            # ----------------------------------
            # Check if word is valid (contd.)
            # ----------------------------------
            if future:
                result: int = self.get_query_response(future)

                if result == bot.API_RESPONSE_WORD_DOESNT_EXIST:

                    if self.server_configs[server_id].current_word:
                        response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered does not exist.*
{f'The chain length was {self.server_configs[server_id].current_count} when it was broken. :sob:\n' if self.server_configs[server_id].current_count > 0 else ''}\
Restart with a word starting with **{self.server_configs[server_id].current_word[-1]}** and try to beat the \
current high score of **{self.server_configs[server_id].high_score}**!'''

                    else:
                        response: str = f'''{message.author.mention} messed up the chain! \
*The word you entered does not exist.*
Restart and try to beat the current high score of **{self.server_configs[server_id].high_score}**!'''

                    await self.handle_mistake(message, response, connection)
                    await connection.commit()
                    return

                elif result == bot.API_RESPONSE_ERROR:

                    await message.add_reaction('⚠️')
                    await message.channel.send(''':octagonal_sign: There was an issue in the backend.
The above entered word is **NOT** being taken into account.''')
                    return

            # --------------------
            # Everything is fine
            # ---------------------
            self.server_configs[server_id].update_current(member_id=message.author.id, current_word=word)

            await message.add_reaction(
                SPECIAL_REACTION_EMOJIS.get(word, self.server_configs[server_id].reaction_emoji()))

            last_words: deque[str] = self._server_histories[server_id][message.author.id]
            karma: float = calculate_total_karma(word, last_words)
            self._server_histories[server_id][message.author.id].append(word)

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
                word=word
            )
            await connection.execute(stmt)

            current_count = self.server_configs[server_id].current_count

            if current_count > 0 and current_count % 100 == 0:
                await message.channel.send(f'{current_count} words! Nice work, keep it up!')

            # Check and reset the server config.failed_member_id to None.
            if self.server_failed_roles[server_id] and self.server_configs[
                server_id].failed_member_id == message.author.id:
                self.server_configs[server_id].correct_inputs_by_failed_member += 1
                if self.server_configs[server_id].correct_inputs_by_failed_member >= 30:
                    self.server_configs[server_id].failed_member_id = None
                    self.server_configs[server_id].correct_inputs_by_failed_member = 0
                    await self.add_remove_failed_role(message.guild, connection)

            await self.add_to_cache(word, connection)
            await self.add_remove_reliable_role(message.guild, connection)
            await self.server_configs[server_id].sync_to_db_with_connection(connection)

            await connection.commit()

    # ---------------------------------------------------------------------------------------------------------------

    async def handle_mistake(self, message: discord.Message,
                             response: str, connection: AsyncConnection) -> None:
        """Handles when someone messes up the count with a wrong number"""

        server_id = message.guild.id
        member_id = message.author.id
        if self.server_failed_roles[server_id]:
            self.server_configs[server_id].failed_member_id = member_id  # Designate current user as failed member
            await self.add_remove_failed_role(message.guild, connection)

        self.server_configs[server_id].fail_chain(member_id)

        await message.channel.send(response)
        await message.add_reaction('❌')

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
            UsedWordsModel.server_id == server_id
        )
        await connection.execute(stmt)

        await self.server_configs[server_id].sync_to_db_with_connection(connection)


    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def start_api_query(word: str) -> concurrent.futures.Future:
        """
        Starts a Wiktionary API query in the background to find the given word.

        Parameters
        ----------
        word : str
             The word to be searched for.

        Returns
        -------
        concurrent.futures.Future
              A Futures object for the API query.
        """

        session: FuturesSession = FuturesSession()

        url: str = "https://en.wiktionary.org/w/api.php"
        params: dict = {
            "action": "opensearch",
            "namespace": "0",
            "search": word,
            "limit": "2",
            "format": "json",
            "profile": "strict"
        }

        return session.get(url=url, params=params)

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def get_query_response(future: concurrent.futures.Future) -> int:
        """
        Get the result of a query that was started in the background.

        Parameters
        ----------
        future : concurrent.futures.Future
            The Future object corresponding to the started API query.

        Returns
        -------
        int
            `bot.API_RESPONSE_WORD_EXISTS` is the word exists, `bot.API_RESPONSE_WORD_DOESNT_EXIST` if the word
            does not exist, or `bot.API_RESPONSE_ERROR` if an error (of any type) was raised in the query.
        """
        try:
            response = future.result(timeout=5)

            if response.status_code >= 400:
                logger.error(f'Received status code {response.status_code} from Wiktionary API query.')
                return bot.API_RESPONSE_ERROR

            data = response.json()

            word: str = data[0]
            best_match: str = data[1][0]  # Should raise an IndexError if no match is returned

            if best_match.lower() == word.lower():
                return bot.API_RESPONSE_WORD_EXISTS
            else:
                # Normally, the control should not reach this else statement.
                # If, however, some word is returned by chance, and it doesn't match the entered word,
                # this else will take care of it
                return bot.API_RESPONSE_WORD_DOESNT_EXIST

        except TimeoutError:  # Send bot.API_RESPONSE_ERROR
            logger.error('Timeout error raised when trying to get the query result.')
        except IndexError:
            return bot.API_RESPONSE_WORD_DOESNT_EXIST
        except Exception as ex:
            logger.error(f'An exception was raised while getting the query result:\n{ex}')

        return bot.API_RESPONSE_ERROR

    # ---------------------------------------------------------------------------------------------------------------

    async def on_message_delete(self, message: discord.Message) -> None:
        """Post a message in the channel if a user deletes their input."""

        if not self.is_ready():
            return

        if message.author == self.user:
            return

        # Check if the message is in the channel
        if message.channel.id != self.server_configs[message.guild.id].channel_id:
            return
        if not message.reactions:
            return
        if not all(c in POSSIBLE_CHARACTERS for c in message.content.lower()):
            return

        if self.server_configs[message.guild.id].current_word:
            await message.channel.send(
                f'{message.author.mention} deleted their word! '
                f'The **last** word was **{self.server_configs[message.guild.id].current_word}**.')
        else:
            await message.channel.send(f'{message.author.mention} deleted their word!')

    # ---------------------------------------------------------------------------------------------------------------

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Send a message in the channel if a user modifies their input."""

        if not self.is_ready():
            return

        if before.author == self.user:
            return

        # Check if the message is in the channel
        if before.channel.id != self.server_configs[before.guild.id].channel_id:
            return
        if not before.reactions:
            return
        if not all(c in POSSIBLE_CHARACTERS for c in before.content.lower()):
            return
        if before.content.lower() == after.content.lower():
            return

        if self.server_configs[before.guild.id].current_word:
            await after.channel.send(
                f'{after.author.mention} edited their word! '
                f'The **last** word was **{self.server_configs[before.guild.id].current_word}**.')
        else:
            await after.channel.send(f'{after.author.mention} edited their word!')

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def is_word_in_cache(word: str, connection: AsyncConnection) -> bool:
        """
        Check if a word is in the correct word cache schema.

        Note that if this returns `True`, then the word is definitely correct. But, if this returns `False`, it
        only means that the word does not yet exist in the schema. It does NOT mean that the word is wrong.

        Parameters
        ----------
        word : str
            The word to be searched for in the schema.
        connection : AsyncConnection
            The Cursor object to access the schema.

        Returns
        -------
        bool
            `True` if the word exists in the cache, otherwise `False`.
        """
        stmt = select(exists(WordCacheModel).where(WordCacheModel.word == word))
        result: CursorResult = await connection.execute(stmt)
        return result.scalar()

    # ---------------------------------------------------------------------------------------------------------------

    async def add_to_cache(self, word: str, connection: AsyncConnection) -> None:
        """
        Add a word into the `bot.TABLE_CACHE` schema.
        """
        if not await self.is_word_blacklisted(word):  # Do NOT insert globally blacklisted words into the cache
            stmt = insert(WordCacheModel).values(word=word).prefix_with('OR IGNORE')
            await connection.execute(stmt)

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def is_word_blacklisted(word: str, server_id: Optional[int] = None,
                                  connection: Optional[AsyncConnection] = None) -> bool:
        """
        Checks if a word is blacklisted.

        Checking hierarchy:
        1. Global blacklists/whitelists, THEN
        2. Server blacklist.

        Do not pass the `server_id` or `connection` instance if you want to query the global blacklists only.

        Parameters
        ----------
        word : str
            The word that is to be checked.
        server_id : Optional[int] = None
            The guild which is calling this function. Default: `None`.
        connection : Optional[AsyncConnection] = None
            An instance of AsyncConnection through which the DB will be accessed. Default: `None`.

        Returns
        -------
        bool
            `True` if the word is blacklisted, otherwise `False`.
        """
        # Check global blacklists
        if word in GLOBAL_BLACKLIST_2_LETTER_WORDS or word in GLOBAL_BLACKLIST_N_LETTER_WORDS:
            return True

        # Check global 3-letter words WHITElist
        if len(word) == 3 and word not in GLOBAL_WHITELIST_3_LETTER_WORDS:
            return True

        # Either of these two params being null implies only the global blacklists should be checked
        if server_id is None or connection is None:
            # Global blacklists have already been checked. If the control is here, it means that
            # the word is not globally blacklisted. So, return False.
            return False

        # Check server blacklist
        stmt = select(exists(BlacklistModel).where(
            BlacklistModel.server_id == server_id,
            BlacklistModel.word == word
        ))
        result: CursorResult = await connection.execute(stmt)
        return result.scalar()

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def is_word_whitelisted(word: str, server_id: int, connection: AsyncConnection) -> bool:
        """
        Checks if a word is whitelisted.

        Note that whitelist has higher priority than blacklist.

        Parameters
        ----------
        word : str
            The word that is to be checked.
        server_id : int
            The guild which is calling this function.
        connection : AsyncConnection
            An instance of AsyncConnection through which the DB will be accessed.

        Returns
        -------
        bool
            `True` if the word is whitelisted, otherwise `False`.
        """
        # Check server whitelisted
        stmt = select(exists(WhitelistModel).where(
            WhitelistModel.server_id == server_id,
            WhitelistModel.word == word
        ))
        result: CursorResult = await connection.execute(stmt)
        return result.scalar()

    # ---------------------------------------------------------------------------------------------------------------

    async def setup_hook(self) -> None:
        if not DEV_MODE:
            # only sync when not in dev mode to avoid syncing over and over again - use sync command explicitly
            global_sync = await self.tree.sync()
            admin_sync = await self.tree.sync(guild=discord.Object(id=ADMIN_GUILD_ID))
            logger.info(f'Synchronized {len(global_sync)} global commands and {len(admin_sync)} admin commands')

        alembic_cfg = AlembicConfig('alembic.ini')
        alembic_command.upgrade(alembic_cfg, 'head')

bot = Bot()


@bot.tree.command(name='sync', description='Syncs the slash commands to the bot')
@app_commands.guilds(ADMIN_GUILD_ID)
@app_commands.default_permissions(ban_members=True)
async def sync(interaction: discord.Interaction):
    """Sync all the slash commands to the bot"""
    await interaction.response.defer()
    global_sync = await bot.tree.sync()
    admin_sync = await bot.tree.sync(guild=discord.Object(id=ADMIN_GUILD_ID))
    await interaction.followup.send(f'Synchronized {len(global_sync)} global commands and {len(admin_sync)} admin commands')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='clean_server', description='Removes all config data for given guild id.')
@app_commands.guilds(ADMIN_GUILD_ID)
@app_commands.describe(guild_id='ID of the guild to be removed from the DB')
@app_commands.default_permissions(manage_guild=True)
async def clean_server(interaction: discord.Interaction, guild_id: str):
    await interaction.response.defer()

    # cannot use int directly in type annotation, because it would allow just 32-bit integers, but most IDs are 64-bit
    try:
        guild_id_as_number = int(guild_id)
    except ValueError:
        await interaction.followup.send('This is not a valid ID!')
        return

    async with bot.db_connection() as connection:
        total_rows_changed = 0

        # delete used words
        stmt = delete(UsedWordsModel).where(UsedWordsModel.server_id == guild_id_as_number)
        result = await connection.execute(stmt)
        total_rows_changed += result.rowcount

        # delete members
        stmt = delete(MemberModel).where(MemberModel.server_id == guild_id_as_number)
        result = await connection.execute(stmt)
        total_rows_changed += result.rowcount

        # delete blacklist
        stmt = delete(BlacklistModel).where(BlacklistModel.server_id == guild_id_as_number)
        result = await connection.execute(stmt)
        total_rows_changed += result.rowcount

        # delete whitelist
        stmt = delete(WhitelistModel).where(WhitelistModel.server_id == guild_id_as_number)
        result = await connection.execute(stmt)
        total_rows_changed += result.rowcount

        # delete config
        if guild_id_as_number in bot.server_configs:
            # just reset the data instead to make sure that every current guild has an existing config
            config = bot.server_configs[guild_id_as_number]
            config.channel_id = None
            config.current_count = 0
            config.current_word = None
            config.high_score = 0
            config.used_high_score_emoji = False
            config.reliable_role_id = None
            config.failed_role_id = None
            config.last_member_id = None
            config.failed_member_id = None
            config.correct_inputs_by_failed_member = 0

            total_rows_changed += await config.sync_to_db_with_connection(connection)
        else:
            stmt = delete(ServerConfigModel).where(ServerConfigModel.server_id == guild_id_as_number)
            result = await connection.execute(stmt)
            total_rows_changed += result.rowcount

        await connection.commit()

        if total_rows_changed > 0:
            await interaction.followup.send(f'Removed data for server {guild_id_as_number}')
        else:
            await interaction.followup.send(f'No data to remove for server {guild_id_as_number}')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='clean_user', description='Removes all saved data for given user id.')
@app_commands.guilds(ADMIN_GUILD_ID)
@app_commands.describe(user_id='ID of the user to be removed from the DB')
@app_commands.default_permissions(manage_guild=True)
async def clean_user(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer()

    # cannot use int directly in type annotation, because it would allow just 32-bit integers, but most IDs are 64-bit
    try:
        user_id_as_number = int(user_id)
    except ValueError:
        await interaction.followup.send('This is not a valid ID!')
        return

    async with bot.db_connection() as connection:
        stmt = delete(MemberModel).where(MemberModel.member_id == user_id_as_number)
        result = await connection.execute(stmt)
        await connection.commit()
        rows_deleted: int = result.rowcount
        if rows_deleted > 0:
            await interaction.followup.send(f'Removed data for user {user_id_as_number} in {rows_deleted} servers')
        else:
            await interaction.followup.send(f'No data to remove for user {user_id_as_number}')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='set_channel', description='Sets the channel to count in')
@app_commands.describe(channel='The channel to count in')
@app_commands.default_permissions(manage_guild=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Command to set the channel to count in"""
    await interaction.response.defer()

    bot.server_configs[interaction.guild.id].channel_id = channel.id
    await bot.server_configs[interaction.guild.id].sync_to_db(bot.db_connection)

    await interaction.followup.send(f'Word chain channel was set to {channel.mention}')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='list_commands', description='List all slash commands')
@app_commands.describe(ephemeral="Whether the list will be publicly displayed")
async def list_commands(interaction: discord.Interaction, ephemeral: bool = True):
    """Command to list all the slash commands"""

    await interaction.response.defer()

    emb = discord.Embed(title='Slash Commands', color=discord.Color.blue(),
                        description='''
**list_commands** - Lists all the slash commands.
**stats user** - Shows the stats of a specific user.
**stats server** - Shows the stats of the server.
**check_word** - Check if a word exists/check the spelling.
**leaderboard** - Shows the leaderboard of the server.''')

    if interaction.user.guild_permissions.ban_members:
        emb.description += '''\n
__Restricted commands__ (Admin-only)
**sync** - Syncs the slash commands to the bot.
**set_channel** - Sets the channel to chain words.
**set_failed_role** - Sets the role to give when a user fails.
**set_reliable_role** - Sets the reliable role.
**remove_failed_role** - Unsets the role to give when a user fails.
**remove_reliable_role** - Unset the reliable role.
**prune** - Remove data for users who are no longer in the server.
**blacklist add** - Add a word to the blacklist for this server.
**blacklist remove** - Remove a word from the blacklist of this server.
**blacklist show** - Show the blacklisted words for this server.
**whitelist add** - Add a word to the whitelist for this server.
**whitelist remove** - Remove a word from the whitelist of this server.
**whitelist show** - Show the whitelist words for this server.'''

    await interaction.followup.send(embed=emb, ephemeral=ephemeral)

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='check_word', description='Check if a word is correct')
@app_commands.describe(word='The word to check')
async def check_word(interaction: discord.Interaction, word: str):
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
    await interaction.response.defer()

    emb = discord.Embed(color=discord.Color.blurple())

    if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
        emb.description = f'❌ **{word}** is **not** a legal word.'
        await interaction.followup.send(embed=emb)
        return

    if len(word) == 1:
        emb.description = f'❌ **{word}** is **not** a valid word.'
        await interaction.followup.send(embed=emb)
        return

    word = word.lower()

    async with bot.db_connection() as connection:
        if await bot.is_word_whitelisted(word, interaction.guild.id, connection):
            emb.description = f'✅ The word **{word}** is valid.'
            await interaction.followup.send(embed=emb)
            return

        if await bot.is_word_blacklisted(word, interaction.guild.id, connection):
            emb.description = f'❌ The word **{word}** is **blacklisted** and hence, **not** valid.'
            await interaction.followup.send(embed=emb)
            return

        if await bot.is_word_in_cache(word, connection):
            emb.description = f'✅ The word **{word}** is valid.'
            await interaction.followup.send(embed=emb)
            return

        future: concurrent.futures.Future = bot.start_api_query(word)

        match bot.get_query_response(future):
            case bot.API_RESPONSE_WORD_EXISTS:

                emb.description = f'✅ The word **{word}** is valid.'

                await bot.add_to_cache(word, connection)

            case bot.API_RESPONSE_WORD_DOESNT_EXIST:
                emb.description = f'❌ **{word}** is **not** a valid word.'
            case _:
                emb.description = f'⚠️ There was an issue in fetching the result.'

        await interaction.followup.send(embed=emb)

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='set_failed_role',
                  description='Sets the role to be used when a user puts a wrong word')
@app_commands.describe(role='The role to be used when a user puts a wrong word')
@app_commands.default_permissions(manage_guild=True)
async def set_failed_role(interaction: discord.Interaction, role: discord.Role):
    """Command to set the role to be used when a user fails to count"""
    await interaction.response.defer()

    guild_id = interaction.guild.id
    bot.server_configs[guild_id].failed_role_id = role.id

    async with bot.db_connection() as connection:
        await bot.server_configs[guild_id].sync_to_db_with_connection(connection)
        bot.server_failed_roles[guild_id] = role  # Assign role directly if we already have it in this context
        await bot.add_remove_failed_role(interaction.guild, connection)
        await connection.commit()
        await interaction.followup.send(f'Failed role was set to {role.mention}')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='set_reliable_role',
                  description='Sets the role to be used when a user attains a score of 100')
@app_commands.describe(role='The role to be used when a user attains a score of 100')
@app_commands.default_permissions(manage_guild=True)
async def set_reliable_role(interaction: discord.Interaction, role: discord.Role):
    """Command to set the role to be used when a user gets 100 of score"""
    await interaction.response.defer()

    guild_id = interaction.guild.id
    bot.server_configs[guild_id].reliable_role_id = role.id

    async with bot.db_connection() as connection:
        await bot.server_configs[guild_id].sync_to_db_with_connection(connection)
        bot.server_reliable_roles[guild_id] = role  # Assign role directly if we already have it in this context
        await bot.add_remove_reliable_role(interaction.guild, connection)
        await connection.commit()

        await interaction.followup.send(f'Reliable role was set to {role.mention}')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='remove_failed_role', description='Removes the failed role feature')
@app_commands.default_permissions(manage_guild=True)
async def remove_failed_role(interaction: discord.Interaction):
    await interaction.response.defer()

    guild_id = interaction.guild.id
    bot.server_configs[guild_id].failed_role_id = None
    bot.server_configs[guild_id].failed_member_id = None
    bot.server_configs[guild_id].correct_inputs_by_failed_member = 0
    await bot.server_configs[guild_id].sync_to_db(bot.db_connection)

    if bot.server_failed_roles[guild_id]:
        role = bot.server_failed_roles[guild_id]
        for member in role.members:
            await member.remove_roles(role)
        bot.server_failed_roles[guild_id] = None
        await interaction.followup.send('Failed role removed')
    else:
        await interaction.followup.send('Failed role was already removed')

# ---------------------------------------------------------------------------------------------------------------


@bot.tree.command(name='remove_reliable_role', description='Removes the reliable role feature')
@app_commands.default_permissions(manage_guild=True)
async def remove_reliable_role(interaction: discord.Interaction):
    await interaction.response.defer()

    guild_id = interaction.guild.id
    bot.server_configs[guild_id].reliable_role_id = None
    await bot.server_configs[guild_id].sync_to_db(bot.db_connection)

    if bot.server_reliable_roles[guild_id]:
        role = bot.server_reliable_roles[guild_id]
        for member in role.members:
            await member.remove_roles(role)
        bot.server_reliable_roles[guild_id] = None
        await interaction.followup.send('Reliable role removed')
    else:
        await interaction.followup.send('Reliable role was already removed')

# ---------------------------------------------------------------------------------------------------------------

"""
@bot.tree.command(name='prune', description='(DANGER) Deletes data of users who are no longer in the server')
@app_commands.default_permissions(administrator=True)
async def prune(interaction: discord.Interaction):
    await interaction.response.defer()

    async with bot.SQL_ENGINE.begin() as connection:
        stmt = select(MemberModel.member_id).where(MemberModel.server_id == interaction.guild.id)
        result: CursorResult = await connection.execute(stmt)
        data: Sequence[Row[tuple[int]]] = result.fetchall()

        if data:
            member_count: int = 0

            for entry in data:
                user_id: int = entry[0]

                if interaction.guild.get_member(user_id) is None:
                    stmt = delete(MemberModel).where(
                        MemberModel.server_id == interaction.guild.id,
                        MemberModel.member_id == user_id
                    )
                    await connection.execute(stmt)
                    member_count += 1
                    logger.info(f'Removed data for user {user_id}.')

            if member_count > 0:
                await connection.commit()
                await interaction.followup.send(f'Successfully removed data for {member_count} user(s).')
            else:
                await interaction.followup.send('No users met the criteria to be removed.')

        else:
            await interaction.followup.send('No users found in the database.')
"""

# ===================================================================================================================


class LeaderboardCmdGroup(app_commands.Group):

    def __init__(self):
        super().__init__(name='leaderboard')

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='Shows the first 10 users with the highest score/karma')
    @app_commands.describe(metric='Use either score or karma for ordering the leaderboard')
    @app_commands.choices(metric=[
        app_commands.Choice(name='score', value='score'),
        app_commands.Choice(name='karma', value='karma')
    ])
    @app_commands.describe(scope='Use either users from the current server or all users globally for the leaderboard')
    @app_commands.choices(scope=[
        app_commands.Choice(name='server', value='server'),
        app_commands.Choice(name='global', value='global')
    ])
    async def user(self, interaction: discord.Interaction, metric: Optional[app_commands.Choice[str]],
                   scope: Optional[app_commands.Choice[str]]):
        """Command to show the top 10 users with the highest score/karma."""
        await interaction.response.defer()

        board_metric: str = 'score' if metric is None else metric.value
        board_scope: str = 'server' if scope is None else scope.value

        emb = discord.Embed(
            title=f'Top 10 users by {board_metric}',
            color=discord.Color.blue(),
            description=''
        )

        match board_scope:
            case 'server':
                emb.set_author(name=interaction.guild.name,
                               icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            case 'global':
                emb.set_author(name='Global')

        async with bot.db_connection(locked=False) as connection:
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
                            .order_by(field.desc())
                            .limit(limit))
                case 'global':
                    stmt = (select(MemberModel.member_id, func.sum(field))
                            .group_by(MemberModel.member_id)
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
    async def server(self, interaction: discord.Interaction):
        """Command to show the top 10 servers with the highest highscore"""
        await interaction.response.defer()

        emb = discord.Embed(
            title=f'Top 10 servers by highscore',
            color=discord.Color.blue(),
            description=''
        ).set_author(name='Global')

        async with bot.db_connection(locked=False) as connection:
            limit = 10

            stmt = (select(ServerConfigModel.server_id, ServerConfigModel.high_score)
                    .order_by(ServerConfigModel.high_score.desc())
                    .limit(limit))

            result: CursorResult = await connection.execute(stmt)
            data: Sequence[Row[tuple[int, int]]] = result.fetchall()

            guild_names = defaultdict(lambda: 'unknown', {g.id: g.name for g in bot.guilds})
            for i, server_data in enumerate(data, 1):
                server_id, high_score = server_data
                emb.description += f'{i}. {guild_names[server_id]} **{high_score}**\n'

            await interaction.followup.send(embed=emb)

# ===================================================================================================================


class StatsCmdGroup(app_commands.Group):

    def __init__(self):
        super().__init__(name='stats')

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='Show the server stats for the word chain game')
    async def server(self, interaction: discord.Interaction) -> None:
        """Command to show the stats of the server"""
        await interaction.response.defer()

        config: ServerConfig = bot.server_configs[interaction.guild.id]

        if config.channel_id is None:  # channel not set yet
            await interaction.followup.send("Counting channel not set yet!")
            return

        server_stats_embed = discord.Embed(
            description=f'''Current Chain Length: {config.current_count}
Longest chain length: {config.high_score}
{f"**Last word:** {config.current_word}" if config.current_word else ""}
{f"Last word by: <@{config.last_member_id}>" if config.last_member_id else ""}''',
            color=discord.Color.blurple()
        )
        server_stats_embed.set_author(name=interaction.guild, icon_url=interaction.guild.icon if interaction.guild.icon else None)

        await interaction.followup.send(embed=server_stats_embed)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='Show the user stats for the word chain game')
    @app_commands.describe(member="The user whose stats you want to see")
    async def user(self, interaction: discord.Interaction, member: Optional[discord.Member]) -> None:
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

        async with bot.db_connection(locked=False) as connection:
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


@app_commands.default_permissions(ban_members=True)
class BlacklistCmdGroup(app_commands.Group):

    def __init__(self):
        super().__init__(name='blacklist')

    # ---------------------------------------------------------------------------------------------------------------

    # subcommand of Group
    @app_commands.command(description='Add a word to the blacklist')
    @app_commands.describe(word="The word to be added to the blacklist")
    async def add(self, interaction: discord.Interaction, word: str) -> None:
        await interaction.response.defer()

        emb: discord.Embed = discord.Embed(colour=discord.Color.blurple())

        if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
            emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
            await interaction.followup.send(embed=emb)
            return

        async with bot.db_connection() as connection:
            stmt = insert(BlacklistModel).values(
                server_id=interaction.guild.id,
                word=word.lower()
            ).prefix_with('OR IGNORE')
            await connection.execute(stmt)
            await connection.commit()

        emb.description = f'✅ The word *{word.lower()}* was successfully added to the blacklist.'
        await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='Remove a word from the blacklist')
    @app_commands.describe(word='The word to be removed from the blacklist')
    async def remove(self, interaction: discord.Interaction, word: str) -> None:
        await interaction.response.defer()

        emb: discord.Embed = discord.Embed(colour=discord.Color.blurple())

        if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
            emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
            await interaction.followup.send(embed=emb)
            return

        async with bot.db_connection() as connection:
            stmt = delete(BlacklistModel).where(
                BlacklistModel.server_id == interaction.guild.id,
                BlacklistModel.word == word.lower()
            )
            await connection.execute(stmt)
            await connection.commit()

        emb.description = f'✅ The word *{word.lower()}* was successfully removed from the blacklist.'
        await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='List the blacklisted words')
    async def show(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        async with bot.db_connection(locked=False) as connection:
            stmt = select(BlacklistModel.word).where(BlacklistModel.server_id == interaction.guild.id)
            result: CursorResult = await connection.execute(stmt)
            words = [row[0] for row in result]

            emb = discord.Embed(title=f'Blacklisted words', description='', colour=discord.Color.dark_orange())

            if len(words) == 0:
                emb.description = f'No word has been blacklisted in this server.'
                await interaction.followup.send(embed=emb)
            else:
                i: int = 0
                for word in words:
                    i += 1
                    emb.description += f'{i}. {word}\n'

                await interaction.followup.send(embed=emb)


# ================================================================================================================


@app_commands.default_permissions(ban_members=True)
class WhitelistCmdGroup(app_commands.Group):
    """
    Whitelisting a word will make the bot skip the blacklist check and the valid word check for that word.
    Whitelist has higher priority than blacklist.
    This feature can also be used to include words which are not present in the English dictionary.
    """

    def __init__(self):
        super().__init__(name='whitelist')

    # ---------------------------------------------------------------------------------------------------------------

    # subcommand of Group
    @app_commands.command(description='Add a word to the whitelist')
    @app_commands.describe(word="The word to be added")
    async def add(self, interaction: discord.Interaction, word: str) -> None:
        await interaction.response.defer()

        emb: discord.Embed = discord.Embed(colour=discord.Color.blurple())

        if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
            emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
            await interaction.followup.send(embed=emb)
            return

        async with bot.db_connection() as connection:
            stmt = insert(WhitelistModel).values(
                server_id=interaction.guild.id,
                word=word.lower()
            ).prefix_with('OR IGNORE')
            await connection.execute(stmt)
            await connection.commit()

        emb.description = f'✅ The word *{word.lower()}* was successfully added to the whitelist.'
        await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='Remove a word from the whitelist')
    @app_commands.describe(word='The word to be removed')
    async def remove(self, interaction: discord.Interaction, word: str) -> None:
        await interaction.response.defer()

        emb: discord.Embed = discord.Embed(colour=discord.Color.blurple())

        if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
            emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
            await interaction.followup.send(embed=emb)
            return

        async with bot.db_connection() as connection:
            stmt = delete(WhitelistModel).where(
                WhitelistModel.server_id == interaction.guild.id,
                WhitelistModel.word == word.lower()
            )
            await connection.execute(stmt)
            await connection.commit()

        emb.description = f'✅ The word *{word.lower()}* has been removed from the whitelist.'
        await interaction.followup.send(embed=emb)

    # ---------------------------------------------------------------------------------------------------------------

    @app_commands.command(description='List the whitelisted words')
    async def show(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        async with bot.db_connection(locked=False) as connection:
            stmt = select(WhitelistModel.word).where(WhitelistModel.server_id == interaction.guild.id)
            result: CursorResult = await connection.execute(stmt)
            words = [row[0] for row in result]

            emb = discord.Embed(title=f'Whitelisted words', description='', colour=discord.Color.dark_orange())

            if len(words) == 0:
                emb.description = f'No word has been whitelisted in this server.'
                await interaction.followup.send(embed=emb)
            else:
                i: int = 0
                for word in words:
                    i += 1
                    emb.description += f'{i}. {word}\n'

                await interaction.followup.send(embed=emb)


if __name__ == '__main__':
    bot.tree.add_command(LeaderboardCmdGroup())
    bot.tree.add_command(StatsCmdGroup())
    bot.tree.add_command(BlacklistCmdGroup())
    bot.tree.add_command(WhitelistCmdGroup())
    bot.run(os.getenv('TOKEN'), log_handler=None)
