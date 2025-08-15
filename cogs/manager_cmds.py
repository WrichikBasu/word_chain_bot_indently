"""Commands that are available only to server managers."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import discord
from discord import Colour, Embed, Interaction, Permissions, Role, TextChannel, app_commands
from discord.app_commands import Group
from discord.ext.commands import Cog
from sqlalchemy import CursorResult, delete, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from consts import ALLOWED_WORDS_PATTERN, COG_NAME_MANAGER_CMDS, FIRST_TOKEN_SCORES, LOGGER_NAME_MANAGER_COG, GameMode
from model import BlacklistModel, WhitelistModel

if TYPE_CHECKING:
    from main import WordChainBot

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger(LOGGER_NAME_MANAGER_COG)


class ManagerCommandsCog(Cog, name=COG_NAME_MANAGER_CMDS):

    def __init__(self, bot: WordChainBot):
        self.bot: WordChainBot = bot
        self.bot.tree.add_command(ManagerCommandsCog.SetupCommandsGroup(self))
        self.bot.tree.add_command(ManagerCommandsCog.UnsetCommandsGroup(self))
        self.bot.tree.add_command(ManagerCommandsCog.BlacklistCmdGroup(self))
        self.bot.tree.add_command(ManagerCommandsCog.WhitelistCmdGroup(self))

    # ----------------------------------------------------------------------------------------------------------------

    @staticmethod
    def is_generally_illegal_word(word: str):
        return (not re.search(ALLOWED_WORDS_PATTERN, word.lower()) or
                any(word[:game_mode.value] not in FIRST_TOKEN_SCORES[game_mode] or
                    word[-game_mode.value:] not in FIRST_TOKEN_SCORES[game_mode]
                    for game_mode in GameMode)
                )

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

    # =============================================================================================================

    @app_commands.command(name='reset_stats', description='Resets all stats for this server, but keeps the configuration')
    @app_commands.default_permissions(manage_guild=True)
    async def reset_stats(self, interaction: Interaction):

        await interaction.response.defer()

        config = self.bot.server_configs[interaction.guild_id]
        config.game_state[GameMode.NORMAL] = GameModeState()
        config.game_state[GameMode.HARD] = GameModeState()
        config.failed_member_id = None

        async with self.bot.db_connection() as connection:
            try:
                await config.sync_to_db_with_connection(connection)

                stmt = delete(MemberModel).where(
                    MemberModel.server_id == interaction.guild_id
                )

                await connection.execute(stmt)
                await connection.commit()
                emb: Embed = Embed(title='Success', colour=Colour.green(),
                                   description=f'''Stats have been reset.''')
            except SQLAlchemyError as e:
                logger.error(e)
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''There was an error. Changes might not have been saved.''')

        await interaction.followup.send(embed=emb)

    # =============================================================================================================

    class SetupCommandsGroup(Group):

        def __init__(self, parent_cog: ManagerCommandsCog):
            super().__init__(name='set', description='Setup commands',
                             default_permissions=Permissions(manage_guild=True), guild_only=True)
            self.cog: ManagerCommandsCog = parent_cog

        # ------------------------------------------------------------------------------------------------------------

        @app_commands.command(name='reliable_role',
                              description='Sets the role that a user gets upon reaching'
                                          ' a karma of 50 and accuracy > 99%')
        @app_commands.describe(role='The role to be used')
        async def set_reliable_role(self, interaction: Interaction, role: Role):
            """Command to set the role to be used when a user attains 50 karma and accuracy > 99%"""

            await interaction.response.defer()

            bot_member: discord.Member = interaction.guild.me

            if role.position > bot_member.top_role.position:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''You cannot set a role that is higher than my top role 
({bot_member.top_role.mention}) in the hierarchy!''')
                await interaction.followup.send(embed=emb)
                return

            if not bot_member.guild_permissions.manage_roles:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''I do not have the `Manage Roles` permission!''')
                await interaction.followup.send(embed=emb)
                return

            guild_id = interaction.guild.id
            self.cog.bot.server_configs[guild_id].reliable_role_id = role.id

            async with self.cog.bot.db_connection() as connection:
                await self.cog.bot.server_configs[guild_id].sync_to_db_with_connection(connection)
                self.cog.bot.server_reliable_roles[
                    guild_id] = role  # Assign role directly if we already have it in this context
                await self.cog.bot.add_remove_reliable_role(interaction.guild, connection)
                await connection.commit()

                emb: Embed = Embed(title='Success', colour=Colour.green(),
                                   description=f'''Reliable role was set to {role.mention}!''')
                await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------

        @app_commands.command(name='channel', description='Sets the game channel')
        @app_commands.describe(channel='The channel where the game will be played')
        @app_commands.describe(game_mode='Configure either for normal mode or for hard mode')
        async def set_channel(self, interaction: Interaction, channel: TextChannel, game_mode: GameMode):
            """Command to set the play channel"""

            await interaction.response.defer()

            other_game_mode = GameMode.HARD if game_mode == GameMode.NORMAL else GameMode.NORMAL

            if self.cog.bot.server_configs[interaction.guild.id].game_state[other_game_mode].channel_id == channel.id:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''You cannot use a channel for this game mode, that is assigned
to the other game mode!''')
            else:
                self.cog.bot.server_configs[interaction.guild.id].game_state[game_mode].channel_id = channel.id
                await self.cog.bot.server_configs[interaction.guild.id].sync_to_db(self.cog.bot)
                game_mode_name = 'normal game mode' if game_mode == GameMode.NORMAL else 'hard game mode'
                emb: Embed = Embed(title='Success', colour=Colour.green(),
                               description=f'''Word chain channel for {game_mode_name} was set to {channel.mention}.''')

            await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------

        @app_commands.command(name='failed_role',
                              description='Sets the role to be used when a user puts a wrong word')
        @app_commands.describe(role='The role to be used when a user puts a wrong word')
        async def set_failed_role(self, interaction: Interaction, role: Role):
            """Command to set the role to be used when a user fails"""

            await interaction.response.defer()

            bot_member: discord.Member = interaction.guild.me

            if role.position > bot_member.top_role.position:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''You cannot set a role that is higher than my top role 
({bot_member.top_role.mention}) in the hierarchy!''')
                await interaction.followup.send(embed=emb)
                return

            if not bot_member.guild_permissions.manage_roles:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''I do not have the `Manage Roles` permission!''')
                await interaction.followup.send(embed=emb)
                return

            guild_id = interaction.guild.id
            self.cog.bot.server_configs[guild_id].failed_role_id = role.id

            async with self.cog.bot.db_connection() as connection:
                await self.cog.bot.server_configs[guild_id].sync_to_db_with_connection(connection)
                self.cog.bot.server_failed_roles[
                    guild_id] = role  # Assign role directly if we already have it in this context
                await self.cog.bot.add_remove_failed_role(interaction.guild, connection)
                await connection.commit()

                emb: Embed = Embed(title='Success', colour=Colour.green(),
                                   description=f'''Failed role was set to {role.mention}.''')
                await interaction.followup.send(embed=emb)

    # =================================================================================================================

    class UnsetCommandsGroup(Group):

        def __init__(self, parent_cog: ManagerCommandsCog):
            super().__init__(name='unset', description='Resets settings',
                             default_permissions=Permissions(manage_guild=True))
            self.cog: ManagerCommandsCog = parent_cog

        @app_commands.command(name='failed_role', description='Removes the failed role feature')
        async def remove_failed_role(self, interaction: Interaction):

            await interaction.response.defer()

            guild_id = interaction.guild.id
            self.cog.bot.server_configs[guild_id].failed_role_id = None
            self.cog.bot.server_configs[guild_id].failed_member_id = None
            self.cog.bot.server_configs[guild_id].correct_inputs_by_failed_member = 0
            await self.cog.bot.server_configs[guild_id].sync_to_db(self.cog.bot)

            if self.cog.bot.server_failed_roles[guild_id]:
                role = self.cog.bot.server_failed_roles[guild_id]
                for member in role.members:
                    await member.remove_roles(role)
                self.cog.bot.server_failed_roles[guild_id] = None
                emb: Embed = Embed(title='Success', colour=Colour.green(),
                                   description=f'''Failed role has been removed.''')
                await interaction.followup.send(embed=emb)
            else:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''Failed role was already unset!''')
                await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(name='reliable_role', description='Removes the reliable role feature')
        async def remove_reliable_role(self, interaction: Interaction):

            await interaction.response.defer()

            guild_id = interaction.guild.id
            self.cog.bot.server_configs[guild_id].reliable_role_id = None
            await self.cog.bot.server_configs[guild_id].sync_to_db(self.cog.bot)

            if self.cog.bot.server_reliable_roles[guild_id]:
                role = self.cog.bot.server_reliable_roles[guild_id]
                for member in role.members:
                    await member.remove_roles(role)
                self.cog.bot.server_reliable_roles[guild_id] = None
                emb: Embed = Embed(title='Success', colour=Colour.green(),
                                   description=f'''Reliable role has been removed.''')
                await interaction.followup.send(embed=emb)
            else:
                emb: Embed = Embed(title='Error', colour=Colour.red(),
                                   description=f'''Reliable role was already unset!''')
                await interaction.followup.send(embed=emb)

    # ================================================================================================================

    class BlacklistCmdGroup(app_commands.Group):

        def __init__(self, parent_cog: ManagerCommandsCog):
            super().__init__(name='blacklist', description="Blacklist certain words; the bot won't count them",
                             default_permissions=Permissions(manage_guild=True))
            self.cog: ManagerCommandsCog = parent_cog

        # ---------------------------------------------------------------------------------------------------------------

        # subcommand of Group
        @app_commands.command(description='Add a word to the blacklist')
        @app_commands.describe(word="The word to be added to the blacklist")
        async def add(self, interaction: Interaction, word: str) -> None:
            await interaction.response.defer()

            emb: Embed = Embed(colour=Colour.blurple())

            if self.cog.is_generally_illegal_word(word):
                emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
                await interaction.followup.send(embed=emb)
                return

            async with self.cog.bot.db_connection() as connection:
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
        async def remove(self, interaction: Interaction, word: str) -> None:
            await interaction.response.defer()

            emb: Embed = Embed(colour=Colour.blurple())

            if self.cog.is_generally_illegal_word(word):
                emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
                await interaction.followup.send(embed=emb)
                return

            async with self.cog.bot.db_connection() as connection:
                stmt = delete(BlacklistModel).where(
                    BlacklistModel.server_id == interaction.guild.id,
                    BlacklistModel.word == word.lower()
                )
                result = await connection.execute(stmt)
                await connection.commit()

            if result.rowcount == 0:
                emb.description = f'❌ The word *{word.lower()}* is not part of the blacklist.'
            else:
                emb.description = f'✅ The word *{word.lower()}* has been removed from the blacklist.'
            await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='List the blacklisted words')
        async def show(self, interaction: Interaction) -> None:

            await interaction.response.defer()

            async with self.cog.bot.db_connection(locked=False) as connection:
                stmt = select(BlacklistModel.word).where(BlacklistModel.server_id == interaction.guild.id)
                result: CursorResult = await connection.execute(stmt)
                words = [row[0] for row in result]

                emb = Embed(title=f'Blacklisted words', description='', colour=Colour.dark_orange())

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

    class WhitelistCmdGroup(app_commands.Group):
        """
        Whitelisting a word will make the bot skip the blacklist check and the valid word check for that word.
        Whitelist has higher priority than blacklist.
        This feature can also be used to include words which are not present in the English dictionary.
        """

        def __init__(self, parent_cog: ManagerCommandsCog):
            super().__init__(name='whitelist', description="Whitelist certain words; these will take "
                                                           "priority over blacklist",
                             default_permissions=Permissions(manage_guild=True))
            self.cog: ManagerCommandsCog = parent_cog

        # ---------------------------------------------------------------------------------------------------------------

        # subcommand of Group
        @app_commands.command(description='Add a word to the whitelist')
        @app_commands.describe(word="The word to be added")
        async def add(self, interaction: Interaction, word: str) -> None:
            await interaction.response.defer()

            emb: Embed = Embed(colour=Colour.blurple())

            if self.cog.is_generally_illegal_word(word):
                emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
                await interaction.followup.send(embed=emb)
                return

            async with self.cog.bot.db_connection() as connection:
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
        async def remove(self, interaction: Interaction, word: str) -> None:
            await interaction.response.defer()

            emb: Embed = Embed(colour=Colour.blurple())

            if self.cog.is_generally_illegal_word(word):
                emb.description = f'⚠️ The word *{word.lower()}* is not a legal word.'
                await interaction.followup.send(embed=emb)
                return

            async with self.cog.bot.db_connection() as connection:
                stmt = delete(WhitelistModel).where(
                    WhitelistModel.server_id == interaction.guild.id,
                    WhitelistModel.word == word.lower()
                )
                result = await connection.execute(stmt)
                await connection.commit()

            if result.rowcount == 0:
                emb.description = f'❌ The word *{word.lower()}* is not part of the whitelist.'
            else:
                emb.description = f'✅ The word *{word.lower()}* has been removed from the whitelist.'
            await interaction.followup.send(embed=emb)

        # ---------------------------------------------------------------------------------------------------------------

        @app_commands.command(description='List the whitelisted words')
        async def show(self, interaction: Interaction) -> None:
            await interaction.response.defer()

            async with self.cog.bot.db_connection(locked=False) as connection:
                stmt = select(WhitelistModel.word).where(WhitelistModel.server_id == interaction.guild.id)
                result: CursorResult = await connection.execute(stmt)
                words = [row[0] for row in result]

                emb = Embed(title=f'Whitelisted words', description='', colour=Colour.dark_orange())

                if len(words) == 0:
                    emb.description = f'No word has been whitelisted in this server.'
                    await interaction.followup.send(embed=emb)
                else:
                    i: int = 0
                    for word in words:
                        i += 1
                        emb.description += f'{i}. {word}\n'

                    await interaction.followup.send(embed=emb)

# ================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(ManagerCommandsCog(bot))
