import asyncio
import contextlib
import json
import logging
from json import JSONDecodeError
from logging.config import fileConfig
from typing import Any, AsyncIterator

import discord
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from discord import Colour, Embed, Interaction, Object, app_commands
from discord.ext.commands import AutoShardedBot, ExtensionNotLoaded
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

import character_frequency as cf
from consts import (COG_NAME_ADMIN_CMDS, COG_NAME_COMMON, COG_NAME_GAME, COG_NAME_MANAGER_CMDS, COG_NAME_USER_CMDS,
                    COGS_LIST, LOGGER_NAME_MAIN, SETTINGS)

# load logging config from alembic file because it would be loaded anyway when using alembic
fileConfig(fname='config.ini')
logger = logging.getLogger(LOGGER_NAME_MAIN)


class WordChainBot(AutoShardedBot):
    """Word chain bot"""

    __SQL_ENGINE: AsyncEngine = create_async_engine('sqlite+aiosqlite:///database_word_chain.sqlite3')
    __LOCK: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        if SETTINGS.generate_language_on_start:
            logger.info('generating language files on start')
            asyncio.run(cf.main())

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

    async def on_ready(self) -> None:
        """Override the on_ready method"""
        logger.info(f'Bot is ready as {self.user.name}#{self.user.discriminator}')

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
    app_commands.Choice(name='Common', value=COG_NAME_COMMON),
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
