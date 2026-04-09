import asyncio
import concurrent.futures
import contextlib
import inspect
import json
import logging
import os
import re
from asyncio import CancelledError
from collections import defaultdict, deque
from concurrent.futures import Future
from json import JSONDecodeError
from logging.config import fileConfig
from typing import Any, AsyncIterator, List, Optional

import discord
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from discord import Colour, Embed, Interaction, Object, app_commands
from discord.ext.commands import AutoShardedBot, ExtensionNotLoaded
from requests_futures.sessions import FuturesSession
from sqlalchemy import CursorResult, and_, exists, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

import character_frequency as cf
from consts import (COG_NAME_ADMIN_CMDS, COG_NAME_GAME, COG_NAME_MANAGER_CMDS, COG_NAME_USER_CMDS, COGS_LIST,
                    GLOBAL_BLACKLIST_2_LETTER_WORDS_EN, GLOBAL_BLACKLIST_N_LETTER_WORDS_EN, HISTORY_LENGTH,
                    LOGGER_NAME_MAIN, RELIABLE_ROLE_ACCURACY_THRESHOLD, RELIABLE_ROLE_KARMA_THRESHOLD, SETTINGS,
                    GameMode)
from language import Language, LanguageInfo
from model import BlacklistModel, MemberModel, ServerConfig, ServerConfigModel, WhitelistModel, WordCacheModel

# load logging config from alembic file because it would be loaded anyway when using alembic
fileConfig(fname='config.ini')
logger = logging.getLogger(LOGGER_NAME_MAIN)


class WordChainBot(AutoShardedBot):
    """Word chain bot"""

    __SQL_ENGINE: AsyncEngine = create_async_engine('sqlite+aiosqlite:///database_word_chain.sqlite3')
    __LOCK: asyncio.Lock = asyncio.Lock()

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

        if SETTINGS.generate_language_on_start:
            logger.info('generating language files on start')
            asyncio.run(cf.main())

        # maps from server_id -> member_id -> game_mode -> deque
        self.server_histories: dict[int, dict[int, dict[GameMode, deque[str]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: deque(maxlen=HISTORY_LENGTH))))

        self.servers_ready: set[int] = set()

        super().__init__(command_prefix='!', intents=intents)

    # ----------------------------------------------------------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def db_connection(self, locked=True) -> AsyncIterator[AsyncConnection]:
        if locked:
            async with self.__LOCK:
                async with self.__SQL_ENGINE.begin() as connection:
                    yield connection
        else:
            async with self.__SQL_ENGINE.begin() as connection:
                yield connection

    # ---------------------------------------------------------------------------------------------------------------

    async def _rejoin(self, config: ServerConfig, guild: discord.Guild, main_description: str) -> None:
        """
        Handles the complete workflow of making a guild ready.
        This includes:
        - loading discord roles
        - sending a message with the last word
          - if there were messages sent after the last word that were potentially not registered
          - or if the last message is unavailable
        - marking server as ready which is a precondition for further messages being processed
        """
        self.load_discord_roles(guild)

        for game_mode in GameMode:
            try:
                channel: Optional[discord.TextChannel] = self.get_channel(config.game_state[game_mode].channel_id)
            except discord.errors.HTTPException:
                channel = None

            if channel:
                try:
                    last_message = await channel.fetch_message(channel.last_message_id)
                    if (last_message and
                        last_message.author.id == config.game_state[game_mode].last_member_id and
                        last_message.content.lower() == config.game_state[game_mode].current_word):
                        logger.debug(f'Skipped rejoin message for {guild.name} ({guild.id}) in game mode {game_mode}')
                        continue
                except discord.errors.HTTPException:
                    pass

                emb: discord.Embed = discord.Embed(description=main_description,
                                                   colour=discord.Color.brand_green())

                if config.game_state[game_mode].high_score > 0:
                    emb.description += f'\n\n:fire: Let\'s beat the high score of {config.game_state[game_mode].high_score}! :fire:\n'

                if config.game_state[game_mode].current_word:
                    emb.add_field(name='Last valid word', value=f'{config.game_state[game_mode].current_word}', inline=True)

                    if config.game_state[game_mode].last_member_id:
                        member: Optional[discord.Member] = channel.guild.get_member(config.game_state[game_mode].last_member_id)
                        if member:
                            emb.add_field(name='Last input by', value=f'{member.mention}', inline=True)

                try:
                    await channel.send(embed=emb)
                except discord.errors.HTTPException:
                    logger.info(f'Could not send ready message to {guild.name} ({guild.id}) due to missing permissions.')

        self.servers_ready.add(guild.id)

    # ---------------------------------------------------------------------------------------------------------------

    async def ensure_config(self, guild: discord.Guild, connection: AsyncConnection | None = None) -> None:
        """
        Ensures that a config is present for given guild.
        """
        caller_frame = inspect.currentframe().f_back
        caller_function_name = caller_frame.f_code.co_name
        caller_filename = caller_frame.f_code.co_filename.removeprefix(os.getcwd() + os.sep)
        caller_lineno = caller_frame.f_lineno

        logger.debug(f'{caller_function_name} at {caller_filename}:{caller_lineno} requests ensure_config for {guild.id} (shard {guild.shard_id})')

        if guild.id in self.server_configs:
            logger.debug(f'ensure_config for guild {guild.id} (shard {guild.shard_id}): config already in cache')
            return

        async def _ensure_config(_guild_id: int, _connection: AsyncConnection):
            try:
                new_config = ServerConfig(server_id=_guild_id)
                stmt = insert(ServerConfigModel).values(**new_config.to_sqlalchemy_dict())
                await _connection.execute(stmt)
                self.server_configs[new_config.server_id] = new_config
                logger.warning(f'ensure_config for guild {_guild_id}: new config created')
            except SQLAlchemyError as e:
                if "UNIQUE constraint failed" in str(e):
                    stmt = select(ServerConfigModel).where(ServerConfigModel.server_id == _guild_id)
                    result: CursorResult = await _connection.execute(stmt)
                    configs = [ServerConfig.from_sqlalchemy_row(row) for row in result]
                    if len(configs) == 1:
                        config = configs[0]
                        self.server_configs[config.server_id] = config
                        logger.warning(f'ensure_config for guild {_guild_id} (shard {guild.shard_id}): config loaded from db')
                    else:
                        logger.critical(f'ensure_config for guild {_guild_id} (shard {guild.shard_id}): received {len(configs)} configs from DB')
                else:
                    logger.exception(f'ensure_config for guild {_guild_id} (shard {guild.shard_id}): unexpected DB error')

        if connection is None:
            async with self.db_connection() as managed_connection:
                await _ensure_config(guild.id, managed_connection)
                await managed_connection.commit()
        else:
            await _ensure_config(guild.id, connection)

    # ---------------------------------------------------------------------------------------------------------------

    async def on_ready(self) -> None:
        """Override the on_ready method"""
        logger.info(f'Bot is ready as {self.user.name}#{self.user.discriminator}')

        # load all configs and make sure each guild has one entry
        async with self.db_connection() as connection:
            stmt = select(ServerConfigModel)
            result: CursorResult = await connection.execute(stmt)
            configs = [ServerConfig.from_sqlalchemy_row(row) for row in result]
            self.server_configs = {config.server_id: config for config in configs}

            db_servers = {config.server_id for config in configs}
            current_servers = {guild.id for guild in self.guilds}

            servers_without_config = current_servers - db_servers  # those that do not have a config in the db

            for server_id in servers_without_config:
                new_config = ServerConfig(server_id=server_id)
                stmt = insert(ServerConfigModel).values(**new_config.to_sqlalchemy_dict())
                await connection.execute(stmt)
                logger.debug(f'created config for {server_id} in db')
                self.server_configs[server_id] = new_config

            await connection.commit()

        for (index, guild) in enumerate(self.guilds, start=1):
            config = self.server_configs[guild.id]
            await self._rejoin(config, guild, '**I\'m now online!**')
            if index % 100 == 0 or index == len(self.guilds):
                logger.info(f'{index}/{len(self.guilds)} guilds ready')

        logger.info(f'Loaded {len(self.server_configs)} server configs, running on {len(self.guilds)} servers')

    # ---------------------------------------------------------------------------------------------------------------

    async def on_guild_join(self, guild: discord.Guild):
        """Override the on_guild_join method"""
        logger.info(f'Joined guild {guild.name} ({guild.id})')

        if guild.id in self.server_configs:
            await self._rejoin(self.server_configs[guild.id], guild, '**Welcome back!**')
            logger.info(f'Config already present for {guild.name} ({guild.id})')
            return

        async with self.db_connection() as connection:
            try:
                new_config = ServerConfig(server_id=guild.id)
                stmt = insert(ServerConfigModel).values(**new_config.to_sqlalchemy_dict())
                await connection.execute(stmt)
                await connection.commit()
                self.server_configs[new_config.server_id] = new_config
                self.servers_ready.add(guild.id)
                logger.info(f'Config created for guild {guild.name} ({guild.id})')
            except SQLAlchemyError as e:
                if 'UNIQUE constraint failed' in str(e):
                    stmt = select(ServerConfigModel).where(ServerConfigModel.server_id == guild.id)
                    result: CursorResult = await connection.execute(stmt)
                    configs = [ServerConfig.from_sqlalchemy_row(row) for row in result]
                    if len(configs) == 1:
                        config = configs[0]
                        self.server_configs[config.server_id] = config
                        await self._rejoin(config, guild, '**Welcome back!**')
                        logger.info(f'Config loaded from DB for guild {guild.name} ({guild.id})')
                    else:
                        # this should actually never happen
                        logger.critical(f'unable to insert new config, but DB returned {len(configs)} configs, expected exactly 1 config')
                else:
                    logger.exception('unexpected DB error')

    # ---------------------------------------------------------------------------------------------------------------

    def load_discord_roles(self, guild: discord.Guild):
        """
        Sets the `self.server_failed_roles` and `self.server_reliable_roles` variables.
        """
        # no ensure_config needed here, this is already done in the upper call frame
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
        try:
            role = self.server_reliable_roles[guild.id]
            if role:
                stmt = select(MemberModel.member_id).where(
                    MemberModel.server_id == guild.id,
                    MemberModel.karma > RELIABLE_ROLE_KARMA_THRESHOLD,
                    (MemberModel.correct / (MemberModel.correct + MemberModel.wrong)) > RELIABLE_ROLE_ACCURACY_THRESHOLD
                )
                result: CursorResult = await connection.execute(stmt)
                db_members: set[int] = {row[0] for row in result}
                role_members: set[int] = {member.id for member in role.members}

                only_db_members = db_members - role_members  # those that should have the role but do not
                only_role_members = role_members - db_members  # those that have the role but should not

                for member_id in only_db_members:
                    member: Optional[discord.Member] = guild.get_member(member_id)
                    if member:
                        await member.add_roles(role)

                for member_id in only_role_members:
                    member: Optional[discord.Member] = guild.get_member(member_id)
                    if member:
                        await member.remove_roles(role)

        except discord.Forbidden:
            pass

    # ---------------------------------------------------------------------------------------------------------------

    async def add_remove_failed_role(self, guild: discord.Guild, connection: AsyncConnection):
        """
        Adds the `failed_role` to the user whose id is stored in `failed_member_id`.
        Removes the failed role from all other users.
        Does not proceed if failed role has not been set.
        If `failed_role` is not `None` but `failed_member_id` is `None`, then simply removes
        the failed role from all members who have it currently.
        """
        try:
            role = self.server_failed_roles[guild.id]
            if role:
                handled_member = False
                await self.ensure_config(guild, connection)
                config = self.server_configs[guild.id]
                for member in self.server_failed_roles[guild.id].members:
                    if config.failed_member_id == member.id:
                        # Current failed member already has the failed role, so just continue
                        handled_member = True
                        continue
                    else:
                        # Either failed_member_id is None, or this member is not the current failed member.
                        # In either case, we have to remove the role.
                        await member.remove_roles(role)

                if not handled_member and config.failed_member_id:
                    # Current failed member does not yet have the failed role
                    try:
                        failed_member: discord.Member = await guild.fetch_member(config.failed_member_id)
                        await failed_member.add_roles(role)
                    except discord.NotFound:
                        # Member is no longer in the server
                        config.failed_member_id = None
                        config.correct_inputs_by_failed_member = 0
                        await config.sync_to_db_with_connection(connection)

        except discord.Forbidden:
            pass

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def word_matches_pattern(word: str, language_info: LanguageInfo) -> bool:
        """
        Check if the given word matches the pattern for allowed words.

        Parameters
        ----------
        word : str
            The word to check.
        language_info : LanguageInfo
            Language info to check validity

        Returns
        -------
        bool
            `True` if the word matches the pattern, otherwise `False`.
        """
        return True if re.search(language_info.allowed_word_regex, word.lower()) else False

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    def start_api_queries(word: str, languages: List[Language]) -> List[Future]:
        """
        Starts Wiktionary API queries in the background to find the given word, in each of the
        given languages.

        Parameters
        ----------
        languages : list[Language]
             A list of languages to search in.
        word : str
             The word to be searched for.

        Returns
        -------
        list[concurrent.futures.Future]
              A list of Future objects for the API query, one for each language.
        """
        futures: List[Future] = []

        for language in languages:

            url: str = f"https://{language.value.code}.wiktionary.org/w/api.php"
            params: dict = {
                "action": "opensearch",
                "namespace": "0",
                "search": word,
                "limit": "7",
                "format": "json",
                "profile": "strict"
            }
            headers: dict = {
                "User-Agent": "word-chain-bot"
            }

            session: FuturesSession = FuturesSession()
            future: Future = session.get(url=url, params=params, headers=headers)
            futures.append(future)

        return futures

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
            `WordChainBot.API_RESPONSE_WORD_EXISTS` is the word exists,
            `WordChainBot.API_RESPONSE_WORD_DOESNT_EXIST` if the word does not exist, or
            `WordChainBot.API_RESPONSE_ERROR` if an error (of any type) was raised in the query.
        """
        try:
            response = future.result(timeout=5)

            if response.status_code >= 400:
                logger.error(f'Received status code {response.status_code} from Wiktionary API query.')
                return word_chain_bot.API_RESPONSE_ERROR

            data = response.json()
            word: str = data[0]
            matches: list[str] = data[1]
            # causes StopIteration if nothing matches
            _: str = next((match for match in matches if match.lower() == word.lower()))

            return word_chain_bot.API_RESPONSE_WORD_EXISTS

        except StopIteration:
            return word_chain_bot.API_RESPONSE_WORD_DOESNT_EXIST
        except TimeoutError:  # Send bot.API_RESPONSE_ERROR
            logger.error('Timeout error raised when trying to get the query result.')
        except Exception as ex:
            logger.error(f'An exception was raised while getting the query result:\n{ex}')

        return word_chain_bot.API_RESPONSE_ERROR

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def add_words_to_cache(futures: List[Future], connection: AsyncConnection) -> None:
        """
        From the given list of Future objects, get the results of the queries and
        add the words that were found to the cache.

        Parameters
        ----------
        futures : List[Future]
            A list of Future objects for the API queries.
        connection : AsyncConnection
            The AsyncConnection object to access the db.
        """
        future: Future
        for future in futures:
            try:
                response = future.result(timeout=5)

                if response.status_code >= 400:
                    continue

                data = response.json()
                word: str = data[0]
                matches: list[str] = data[1]
                # causes StopIteration if nothing matches
                _: str = next((match for match in matches if match.lower() == word.lower()))

                lang_code: str = (data[3][0]).split('//')[1].split('.')[0]
                language: Language = Language.from_language_code(lang_code)

                await WordChainBot.add_word_to_cache(word, language, connection)

            except (IndexError, TimeoutError, CancelledError, JSONDecodeError, StopIteration):
                continue

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def is_word_in_cache(word: str, connection: AsyncConnection, languages: List[Language]) -> Language | None:
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
        languages : list[Language]
            A list of languages to search in.

        Returns
        -------
        Language | None
            Language of the word if the word exists in the cache, otherwise `None`.
        """
        stmt = select(WordCacheModel.language).where(
            and_(WordCacheModel.word == word, WordCacheModel.language.in_([language.value.code for language in languages]))
        )
        result: CursorResult = await connection.execute(stmt)
        code: str = str(result.scalar())
        return Language.from_language_code(code) if code else None

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def add_word_to_cache(word: str, language: Language, connection: AsyncConnection) -> None:
        """
        Adds a word to the word cache schema.

        Parameters
        ----------
        word : str
            The word to be added.
        language : Language
            The language the word belongs to.
        connection : AsyncConnection
            The connection to access the schema.
        """
        if not await WordChainBot.is_word_blacklisted(word):  # Do NOT insert globally blacklisted words into the cache
            if not re.search(language.value.allowed_word_regex, word):
                logger.warning(f'The word "{word}" is not a legal word in {language.display_name}, but was tried '
                               f'to be added to the cache for words in that language.')
                return

            stmt = insert(WordCacheModel) \
                   .values(word=word, language=language.value.code) \
                   .prefix_with('OR IGNORE')
            await connection.execute(stmt)

    # ---------------------------------------------------------------------------------------------------------------

    @staticmethod
    async def is_word_blacklisted(word: str, server_id: Optional[int] = None,
                                  connection: Optional[AsyncConnection] = None) -> bool:
        """
        Checks if a word is blacklisted for all languages enabled in the guild.

        Checking hierarchy:
            Is the word an English word?
                ├── Yes
                │   ├── Check global blacklists/whitelists.
                │   └── Check server blacklist.
                └── No
                    └── Check server blacklist.

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

        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # GLOBAL BLACKLISTS & WHITELISTS (English)
        # -----------------------------------------
        # Check these if and only if all letters in
        # the word belong to the English alphabet.
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        if re.search(Language.ENGLISH.value.allowed_word_regex, word):

            if word in GLOBAL_BLACKLIST_2_LETTER_WORDS_EN or word in GLOBAL_BLACKLIST_N_LETTER_WORDS_EN:
                return True

        # +++++++++++++ Global Blacklist and whitelist checking complete ++++++++++++++++++++

        # If the control is here, it means that the word  has neither been globally
        # blacklisted nor whitelisted, or is not an English word.

        # Now, if `server` and `connection` are both not `None`, we proceed to check the server
        # blacklist and whitelist. Otherwise, we return `False`.

        if server_id is None or connection is None:
            return False

        # Check server blacklist
        stmt = select(exists(BlacklistModel).where(
            BlacklistModel.server_id == server_id,
            BlacklistModel.word == word
        ))
        result: CursorResult = await connection.execute(stmt)
        return bool(result.scalar())

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
        return bool(result.scalar())

    # ---------------------------------------------------------------------------------------------------------------

    async def setup_hook(self) -> None:

        for cog_name in COGS_LIST:
            await self.load_extension(f'cogs.{cog_name}')

        signature = load_command_signature()

        admin_guild = Object(id=SETTINGS.admin_guild_id)

        global_payload = [command.to_dict(self.tree) for command in self.tree.get_commands()]
        admin_payload = [command.to_dict(self.tree) for command in self.tree.get_commands(guild=admin_guild)]

        global_changed = signature['global_commands'] != global_payload
        admin_changed = signature['admin_commands'] != admin_payload

        if global_changed:
            global_sync = await self.tree.sync()
            logger.info(f'Synchronized {len(global_sync)} global commands')
        else:
            logger.info('No changes in global commands detected')

        if admin_changed:
            admin_sync = await self.tree.sync(guild=admin_guild)
            logger.info(f'Synchronized {len(admin_sync)} admin commands')
        else:
            logger.info('No changes in admin commands detected')

        if global_changed or admin_changed:
            store_command_signature(global_payload, admin_payload)

        alembic_cfg = AlembicConfig('config.ini')
        alembic_command.upgrade(alembic_cfg, 'head')


word_chain_bot: WordChainBot = WordChainBot()


# ===================================================================================================================


def load_command_signature() -> dict:
    try:
        with open(SETTINGS.command_signature_file,'r') as f:
            signature = json.load(f)
    except (JSONDecodeError, FileNotFoundError):
        logger.error('Failed to load existing command signature')
        signature = {
            'global_commands': [],
            'admin_commands': []
        }
    return signature


def store_command_signature(global_commands: list[dict[str, Any]], admin_commands: list[dict[str, Any]]):
    with open(SETTINGS.command_signature_file, 'w') as f:
        signature = {
            'global_commands': global_commands,
            'admin_commands': admin_commands
        }
        json.dump(signature, f)
        logger.info('Dumped latest command signature')


@word_chain_bot.tree.command(name='reload', description='Unload and reload a cog')
@app_commands.guilds(SETTINGS.admin_guild_id)
@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
@app_commands.describe(cog_name='The cog to reload')
@app_commands.choices(cog_name=[
    app_commands.Choice(name='Admin Commands', value=COG_NAME_ADMIN_CMDS),
    app_commands.Choice(name='Manager Commands', value=COG_NAME_MANAGER_CMDS),
    app_commands.Choice(name='User Commands', value=COG_NAME_USER_CMDS),
    app_commands.Choice(name='Game', value=COG_NAME_GAME),
    app_commands.Choice(name='All cogs', value='all')
])
async def reload(interaction: Interaction, cog_name: str, force_sync: bool = False):
    """Reloads a particular cog/all cogs."""

    await interaction.response.defer()

    match cog_name:

        case 'all':
            for cog_name in COGS_LIST:
                try:  # Try to unload each cog
                    await word_chain_bot.unload_extension(f'cogs.{cog_name}')
                except ExtensionNotLoaded:
                    logger.info(f'Extension {cog_name} not loaded.')

                await word_chain_bot.load_extension(f'cogs.{cog_name}')  # Then reload the cog

        case _:
            try:
                await word_chain_bot.unload_extension(f'cogs.{cog_name}')
            except ExtensionNotLoaded:
                logger.info(f'Extension {cog_name} not loaded.')

            await word_chain_bot.load_extension(f'cogs.{cog_name}')

    admin_guild = Object(id=SETTINGS.admin_guild_id)
    global_payload = [command.to_dict(word_chain_bot.tree) for command in word_chain_bot.tree.get_commands()]
    admin_payload = [command.to_dict(word_chain_bot.tree) for command in word_chain_bot.tree.get_commands(guild=admin_guild)]

    emb: Embed = Embed(title=f'Sync status', description=f'Synchronization complete.', colour=Colour.dark_magenta())

    if force_sync:
        global_sync: list[app_commands.AppCommand] | None = await word_chain_bot.tree.sync()
        admin_sync: list[app_commands.AppCommand] | None = await word_chain_bot.tree.sync(guild=admin_guild)

        store_command_signature(global_payload, admin_payload)
    else:
        signature = load_command_signature()
        global_changed = signature['global_commands'] != global_payload
        admin_changed = signature['admin_commands'] != admin_payload

        if global_changed:
            global_sync: list[app_commands.AppCommand] = await word_chain_bot.tree.sync()
        else:
            global_sync = None

        if admin_changed:
            admin_sync: list[app_commands.AppCommand] = await word_chain_bot.tree.sync(guild=admin_guild)
        else:
            admin_sync = None

        if global_changed or admin_changed:
            store_command_signature(global_payload, admin_payload)

    emb.add_field(name="Global commands", value=f"{len(global_sync)}" if global_sync else "SKIPPED")
    emb.add_field(name="Admin commands", value=f"{len(admin_sync)}" if admin_sync else "SKIPPED")

    await interaction.followup.send(embed=emb)


# ===================================================================================================================

if __name__ == '__main__':
    word_chain_bot.run(SETTINGS.token, log_handler=None)
