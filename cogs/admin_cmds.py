"""Commands for bot admins only."""
from __future__ import annotations

import io
import logging
import os
from logging import Logger
from typing import TYPE_CHECKING, Optional

from discord import Colour, Embed, File, Forbidden, Interaction, Object, Permissions, app_commands
from discord.ext.commands import Cog
from dotenv import load_dotenv
from sqlalchemy import delete, insert, select, update

from consts import (COG_NAME_ADMIN_CMDS, LOGGER_NAME_ADMIN_COG, LOGGER_NAME_MAIN, LOGGER_NAME_MANAGER_COG,
                    LOGGER_NAME_USER_COG, LOGGERS_LIST, GameMode)
from model import BannedMemberModel, BlacklistModel, MemberModel, ServerConfigModel, UsedWordsModel, WhitelistModel, \
    ServerConfig

if TYPE_CHECKING:
    from main import WordChainBot

load_dotenv()
ADMIN_GUILD_ID = int(os.environ['ADMIN_GUILD_ID'])

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(LOGGER_NAME_ADMIN_COG)


class AdminCommandsCog(Cog, name=COG_NAME_ADMIN_CMDS):

    def __init__(self, bot: WordChainBot) -> None:
        self.bot: WordChainBot = bot
        self.bot.tree.add_command(AdminCommandsCog.PurgeCmdGroup(self))
        self.bot.tree.add_command(AdminCommandsCog.LoggingControlCmdGroup(self))
        self.bot.tree.add_command(AdminCommandsCog.BanServerCmdGroup(self))
        self.bot.tree.add_command(AdminCommandsCog.BanMemberCmdGroup(self))

    # -----------------------------------------------------------------------------------------------------------------

    def cog_load(self) -> None:
        logger.info(f'Cog {self.qualified_name} loaded.')

    # -----------------------------------------------------------------------------------------------------------------

    def cog_unload(self) -> None:
        logger.info('Removing commands...')

        for command in self.bot.tree.get_commands():  # Loop through all commands in the bot
            if command in self.__cog_commands__:  # And remove the ones that are in the specified cog
                self.bot.tree.remove_command(command.name)

        logger.info(f'Cog {self.qualified_name} unloaded.')

    # -----------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='announce', description='Announce something to all servers')
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(ADMIN_GUILD_ID)
    @app_commands.describe(msg='The message to announce')
    async def announce(self, interaction: Interaction, msg: str):

        await interaction.response.defer()

        emb: Embed = Embed(title='Announcement from devs', description=msg, colour=Colour.yellow())
        emb.description += f'''
\n*For support and updates, join our Discord server:\nhttps://discord.gg/yhbzVGBNw3*
'''
        count_sent: int = 0
        count_failed: int = 0
        for guild in self.bot.guilds:

            config: ServerConfig = self.bot.server_configs[guild.id]

            for game_mode in GameMode:
                if channel := self.bot.get_channel(config.game_state[game_mode].channel_id):
                    try:
                        await channel.send(embed=emb)
                        count_sent += 1
                    except Forbidden as _:
                        logger.error(f'Failed to send announcement to {guild.name} (ID: {guild.id}) due to missing perms.')
                        count_failed += 1

        emb2: Embed = Embed(title='Announcement status', colour=Colour.yellow(), description='Command completed.')
        emb2.add_field(name='Success', value=f'{count_sent} servers', inline=True)
        emb2.add_field(name='Failed', value=f'{count_failed} servers', inline=True)
        await interaction.followup.send(embed=emb2)

    # -----------------------------------------------------------------------------------------------------------------

    @app_commands.command(name='list_servers', description='Lists all servers with ID and name for administration')
    @app_commands.default_permissions(administrator=True)
    @app_commands.guilds(ADMIN_GUILD_ID)
    async def list_servers(self, interaction: Interaction):

        await interaction.response.defer()

        server_entries = [f'{guild.id} ({guild.owner_id}): {guild.name}' for guild in self.bot.guilds]
        file_content = '\n'.join(server_entries).encode('utf-8')
        file_buffer = io.BytesIO(file_content)

        await interaction.followup.send(file=File(file_buffer, 'servers.txt'))

    # ============================================================================================================

    class LoggingControlCmdGroup(app_commands.Group):
        """A group of commands to allow the devs to control logging dynamically without restarting the bot."""

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='logging', description='Admin commands for setting the log level',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='set_level', description='Set the log level for a specific/all logger(s)')
        @app_commands.describe(level='The logging level to be set',
                               logger_name='The logger for which the level has to be set')
        @app_commands.choices(level=[
            app_commands.Choice(name='Debug', value=logging.DEBUG),
            app_commands.Choice(name='Info', value=logging.INFO),
            app_commands.Choice(name='Warning', value=logging.WARNING),
            app_commands.Choice(name='Error', value=logging.ERROR),
            app_commands.Choice(name='Critical', value=logging.CRITICAL)
        ])
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG),
            app_commands.Choice(name='All', value='all')
        ])
        async def set_log_level(self, interaction: Interaction, logger_name: str, level: int):

            await interaction.response.defer()
            emb: Embed = Embed(title='Set log level', colour=Colour.yellow(), description='')

            match logger_name:
                case 'all':
                    for logger_name1 in LOGGERS_LIST:

                        # Retrieve the existing logger; do NOT create a new logger
                        queried_logger: Optional[Logger] = logging.root.manager.loggerDict.get(logger_name1, None)

                        if not queried_logger:
                            emb.description += f'❌ Logger not found.\n'
                            continue

                        emb.description += f'### `{logger_name1}`\n'

                        queried_logger.setLevel(level)
                        emb.description += f'✅ Level set to `{logging.getLevelName(level)}`.\n'

                        if queried_logger.disabled:
                            emb.description += f'⚠️ Logger is disabled!\n\n'
                case _:
                    # Retrieve the existing logger; do NOT create a new logger
                    queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                    emb.description += f'### `{logger_name}`\n'

                    if queried_logger:
                        queried_logger.setLevel(level)
                        emb.description += f'✅ Level set to `{logging.getLevelName(level)}`.'

                        if queried_logger.disabled:
                            emb.description += f'\n\n⚠️ Logger is disabled!'
                    else:
                        emb.description += f'❌ Logger not found.'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='disable_all', description='Disable logging completely')
        async def disable_all(self, interaction: Interaction):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logging status', colour=Colour.green(), description='')

            for logger_name in LOGGERS_LIST:

                # Retrieve the existing logger; do NOT create a new logger
                queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                if queried_logger:
                    if queried_logger.disabled:
                        emb.description += f'☑️ Logger `{queried_logger.name}` was already disabled.\n'
                    else:
                        queried_logger.disabled = True
                        emb.description += f'✅ Disabled logger `{queried_logger.name}`.\n'
                else:
                    emb.description += f'❌ Logger `{logger_name}` not found.\n'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='enable_all', description='Enable all loggers')
        @app_commands.describe(reset_level='Whether to reset the levels of loggers to INFO')
        async def enable_all(self, interaction: Interaction, reset_level: bool = True):

            await interaction.response.defer()

            logging.disable(logging.NOTSET)

            emb: Embed = Embed(title='Logger status', colour=Colour.dark_orange(), description='')

            for logger_name in LOGGERS_LIST:

                # Retrieve the existing logger; do NOT create a new logger
                queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                if queried_logger:
                    if not queried_logger.disabled:
                        emb.description += f'☑️ Logger `{queried_logger.name}` was already enabled.\n'
                    else:
                        queried_logger.disabled = False
                        emb.description += f'✅ Enabled logger `{queried_logger.name}`.\n'

                    if reset_level:
                        queried_logger.setLevel(logging.INFO)
                        emb.description += f'Log level set to `INFO`.\n\n'
                else:
                    emb.description += f'❌ Logger `{logger_name}` not found.\n\n'

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='disable_logger', description='Turn off a specific logger')
        @app_commands.describe(logger_name='The logger for which the level has to be set')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        async def disable_specific_logger(self, interaction: Interaction, logger_name: str):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logger status', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if queried_logger:
                if queried_logger.disabled:
                    emb.description += f'☑️ Logger `{queried_logger.name}` was already disabled.'
                else:
                    queried_logger.disabled = True
                    emb.description += f'✅ Disabled logger `{queried_logger.name}`.'
                emb.colour = Colour.green()
            else:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='enable_logger',
                              description='Turns on a specific logger and sets its level to INFO by default')
        @app_commands.describe(logger_name='The logger for which the level has to be set',
                               reset_level='Whether the level should be explicitly reset to INFO')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        async def enable_specific_logger(self, interaction: Interaction, logger_name: str, reset_level: bool = True):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logger status', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if not queried_logger:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()
            else:
                if not queried_logger.disabled:
                    emb.description += f'☑️ Logger `{queried_logger.name}` was already enabled.'
                else:
                    queried_logger.disabled = False
                    emb.description += f'✅ Enabled logger `{queried_logger.name}`'

                if reset_level:
                    queried_logger.setLevel(logging.INFO)
                    emb.description += f'\n\nLogging level set to `{logging.getLevelName(queried_logger.level)}`.'

                emb.colour = Colour.green()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='test',
                              description='Tests a specific logger')
        @app_commands.describe(logger_name='The logger for which the level has to be set',
                               level='The logging level via which the message will be sent',
                               message='The message to be logged')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG)
        ])
        @app_commands.choices(level=[
            app_commands.Choice(name='Debug', value=logging.DEBUG),
            app_commands.Choice(name='Info', value=logging.INFO),
            app_commands.Choice(name='Warning', value=logging.WARNING),
            app_commands.Choice(name='Error', value=logging.ERROR),
            app_commands.Choice(name='Critical', value=logging.CRITICAL)
        ])
        async def test_logger(self, interaction: Interaction, logger_name: str, message: str,
                              level: int = logging.INFO):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logging Test', description='')

            queried_logger: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
            if not queried_logger:
                emb.description += f'❌ Logger `{logger_name}` not found.'
                emb.colour = Colour.red()
            else:
                if queried_logger.disabled:
                    emb.description += f'❌ Logger `{queried_logger.name}` is disabled.'
                    emb.colour = Colour.red()

                else:
                    queried_logger.log(level=level, msg=message)
                    emb.description += (f'✅ Sent message via `{queried_logger.name}` '
                                        f'at level `{logging.getLevelName(level)}`.')
                    emb.colour = Colour.green()

                    if queried_logger.level > level:
                        emb.description += (f'\n\n⚠️ Message won\'t appear since the logger level is higher than the '
                                            f'message level.')
                        emb.colour = Colour.orange()

            await interaction.followup.send(embed=emb)

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='status',
                              description='Status of a specific/all logger(s)')
        @app_commands.describe(logger_name='The logger for which you want to view the status')
        @app_commands.choices(logger_name=[
            app_commands.Choice(name='Main', value=LOGGER_NAME_MAIN),
            app_commands.Choice(name='Admin Commands', value=LOGGER_NAME_ADMIN_COG),
            app_commands.Choice(name='Manager Commands', value=LOGGER_NAME_MANAGER_COG),
            app_commands.Choice(name='User Commands', value=LOGGER_NAME_USER_COG),
            app_commands.Choice(name='All', value='all')
        ])
        async def logger_status(self, interaction: Interaction, logger_name: str = 'all'):

            await interaction.response.defer()
            emb: Embed = Embed(title='Logger Info', description='', colour=Colour.from_rgb(255, 255, 255))

            match logger_name:
                case 'all':
                    for logger_name1 in LOGGERS_LIST:

                        logger1: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name1, None)
                        emb.description += f'### `{logger_name1}`\n'

                        if logger1:
                            emb.description += f'''> **Status:** {'Disabled' if logger1.disabled else 'Enabled'}
> **Level:** `{logging.getLevelName(logger1.level)}`\n\n'''
                        else:
                            emb.description += f'❌ Logger not found.\n\n'

                case _:
                    logger1: Optional[logging.Logger] = logging.root.manager.loggerDict.get(logger_name, None)
                    emb.description += f'### `{logger1.name}`\n'

                    if logger1:
                        emb.description += f'''> **Status:** {'Disabled' if logger1.disabled else 'Enabled'}
> **Level:** `{logging.getLevelName(logger1.level)}`'''
                    else:
                        emb.description += f'### `{logger_name}`\n'
                        emb.description += f'❌ Logger not found.'

            emb.colour = Colour.green()
            await interaction.followup.send(embed=emb)

    # ============================================================================================================

    class PurgeCmdGroup(app_commands.Group):

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='purge_data', description='Admin commands for cleaning up the DB',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='server', description='Removes all config data for given guild id.')
        @app_commands.describe(guild_id='ID of the guild to be removed from the DB')
        async def clean_server(self, interaction: Interaction, guild_id: str):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                guild_id_as_number = int(guild_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
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
                if guild_id_as_number in self.cog.bot.server_configs:
                    # just reset the data instead to make sure that every current guild has an existing config
                    config = self.cog.bot.server_configs[guild_id_as_number]
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

        @app_commands.command(name='user', description='Removes all saved data for given user id.')
        @app_commands.describe(user_id='ID of the user to be removed from the DB')
        async def clean_user(self, interaction: Interaction, user_id: str):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                user_id_as_number = int(user_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
                stmt = delete(MemberModel).where(MemberModel.member_id == user_id_as_number)
                result = await connection.execute(stmt)
                await connection.commit()
                rows_deleted: int = result.rowcount
                if rows_deleted > 0:
                    await interaction.followup.send(f'Removed data for user {user_id_as_number} in {rows_deleted} servers')
                else:
                    await interaction.followup.send(f'No data to remove for user {user_id_as_number}')

    # ============================================================================================================

    class BanServerCmdGroup(app_commands.Group):

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='ban_server', description='Admin commands for banning servers',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='ban', description='Bans guild with given guild id from leaderboards')
        @app_commands.describe(guild_id='ID of the guild to be banned from leaderboards')
        @app_commands.describe(ban='true to ban the guild, false to unban the guild')
        async def ban(self, interaction: Interaction, guild_id: str, ban: bool = True):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                guild_id_as_number = int(guild_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
                stmt = update(ServerConfigModel).values(
                    is_banned=ban
                ).where(ServerConfigModel.server_id == guild_id_as_number)
                result = await connection.execute(stmt)
                await connection.commit()

                rows_updated: int = result.rowcount
                if rows_updated > 0:
                    self.cog.bot.server_configs[guild_id_as_number].is_banned = ban
                    await interaction.followup.send(f'{'Banned' if ban else 'Unbanned'} server with ID {guild_id_as_number}')
                else:
                    await interaction.followup.send(f'No server found with ID {guild_id_as_number}')

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='list', description='Lists all servers that are currently banned')
        async def list(self, interaction: Interaction):

            await interaction.response.defer()

            async with self.cog.bot.db_connection() as connection:
                stmt = select(ServerConfigModel.server_id).where(ServerConfigModel.is_banned)
                result = await connection.execute(stmt)
                server_ids = [row[0] for row in result]

                if not server_ids:
                    await interaction.followup.send('No servers are banned currently')
                else:
                    server_entries = [f'{server_id}: {self.cog.bot.get_guild(server_id).name if self.cog.bot.get_guild(server_id) is not None else '###'}' for server_id in server_ids]
                    await interaction.followup.send(f'''These servers are currently banned:
* {'\n* '.join(server_entries)}''')

    # ============================================================================================================

    class BanMemberCmdGroup(app_commands.Group):

        def __init__(self, cog: AdminCommandsCog):
            super().__init__(name='ban_member', description='Admin commands for banning servers',
                             guild_ids=[ADMIN_GUILD_ID], guild_only=True,
                             default_permissions=Permissions(administrator=True))
            self.cog: AdminCommandsCog = cog

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='ban', description='Bans member with given member id from playing')
        @app_commands.describe(member_id='ID of the member to be banned from playing')
        @app_commands.describe(ban='true to ban the member, false to unban the member')
        async def ban(self, interaction: Interaction, member_id: str, ban: bool = True):

            await interaction.response.defer()

            # cannot use int directly in type annotation, because it would allow just 32-bit integers,
            # but most IDs are 64-bit
            try:
                member_id_as_number = int(member_id)
            except ValueError:
                await interaction.followup.send('This is not a valid ID!')
                return

            async with self.cog.bot.db_connection() as connection:
                if ban:
                    stmt = insert(BannedMemberModel).values(
                        member_id=member_id_as_number
                    )
                else:
                    stmt = delete(BannedMemberModel).where(
                        BannedMemberModel.member_id == member_id_as_number
                    )

                result = await connection.execute(stmt)
                await connection.commit()

                rows_updated: int = result.rowcount
                if rows_updated > 0:
                    await interaction.followup.send(f'{'Banned' if ban else 'Unbanned'} member with ID {member_id_as_number}')
                else:
                    await interaction.followup.send(f'No member found with ID {member_id_as_number}')

        # -----------------------------------------------------------------------------------------------------------

        @app_commands.command(name='list', description='Lists all members that are currently banned')
        async def list(self, interaction: Interaction):

            await interaction.response.defer()

            async with self.cog.bot.db_connection() as connection:
                stmt = select(BannedMemberModel.member_id)
                result = await connection.execute(stmt)
                member_ids = [row[0] for row in result]

                if not member_ids:
                    await interaction.followup.send('No members are banned currently')
                else:
                    member_entries = [f'{member_id}: {self.cog.bot.get_user(member_id).name if self.cog.bot.get_user(member_id) is not None else '###'}' for member_id in member_ids]
                    await interaction.followup.send(f'''These members are currently banned:
* {'\n* '.join(member_entries)}''')

# ====================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(AdminCommandsCog(bot), guild=Object(id=ADMIN_GUILD_ID))
