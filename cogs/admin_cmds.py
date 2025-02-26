"""Commands for bot admins only."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Optional

from discord import app_commands, Interaction, Object, Permissions, Embed, Colour, TextChannel, Forbidden
from discord.ext.commands import Cog
from dotenv import load_dotenv
from sqlalchemy import delete

from consts import COG_NAME_ADMIN_CMDS
from model import UsedWordsModel, MemberModel, BlacklistModel, WhitelistModel, ServerConfigModel
from utils import db_connection

if TYPE_CHECKING:
    from main import WordChainBot

load_dotenv()
ADMIN_GUILD_ID = int(os.environ['ADMIN_GUILD_ID'])

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(__name__)


class AdminCommandsCog(Cog, name=COG_NAME_ADMIN_CMDS):

    def __init__(self, bot: WordChainBot):

        self.bot: WordChainBot = bot

        self.bot.tree.add_command(AdminCommandsCog.PurgeCmdGroup(self))
        # Add command groups here
        # TODO

    def cog_load(self) -> None:
        logger.info(f'Cog {self.qualified_name} loaded.')

    def cog_unload(self) -> None:
        logger.info(f'Cog {self.qualified_name} unloaded.')

    @app_commands.command(name='announce', description='Announce something to all servers')
    @app_commands.describe(msg='The message to announce')
    async def announce(self, interaction: Interaction, msg: str):

        await interaction.response.defer()

        emb: Embed = Embed(title='Announcement', description=msg, colour=Colour.yellow())
        emb.set_author(name='Word Chain Bot Devs', icon_url=self.bot.get_guild(ADMIN_GUILD_ID).icon.url
                                                            if self.bot.get_guild(ADMIN_GUILD_ID).icon else None)
        emb.description += f'''
\n*For support and updates, join our Discord server:\nhttps://discord.gg/yhbzVGBNw3*
'''
        count_sent: int = 0
        count_failed: int = 0
        for guild in self.bot.guilds:
            config = self.bot.server_configs[guild.id]

            channel: Optional[TextChannel] = self.bot.get_channel(config.channel_id)
            if channel:
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

            async with db_connection(self.cog.bot) as connection:
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

            async with db_connection(self.cog.bot) as connection:
                stmt = delete(MemberModel).where(MemberModel.member_id == user_id_as_number)
                result = await connection.execute(stmt)
                await connection.commit()
                rows_deleted: int = result.rowcount
                if rows_deleted > 0:
                    await interaction.followup.send(f'Removed data for user {user_id_as_number} in {rows_deleted} servers')
                else:
                    await interaction.followup.send(f'No data to remove for user {user_id_as_number}')

# ====================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(AdminCommandsCog(bot), guild=Object(id=ADMIN_GUILD_ID))
