from __future__ import annotations

import concurrent.futures
import logging
import os
from collections import defaultdict
from typing import Optional, Sequence, TYPE_CHECKING

import discord
from discord import app_commands, Interaction, Embed, Colour
from discord.ext.commands import Cog
from sqlalchemy import CursorResult, func, select
from sqlalchemy.engine.row import Row
from sqlalchemy.sql.functions import count
from dotenv import load_dotenv

from consts import *
from model import (Member, MemberModel, ServerConfig, ServerConfigModel)

if TYPE_CHECKING:
    from main import WordChainBot

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
logger: logging.Logger = logging.getLogger(__name__)

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

    @app_commands.command(name='list_commands', description='List all slash commands')
    @app_commands.describe(ephemeral="Whether the list will be publicly displayed")
    async def list_commands(self, interaction: Interaction, ephemeral: bool = True):
        """Command to list all the slash commands"""

        emb = Embed(title='Slash Commands', color=Colour.blue(),
                    description='''
`/list_commands` - Lists all the slash commands.
`/stats` - Shows the stats of a specific user/the current server
`/check_word` - Check if a word exists/check the spelling.
`/leaderboard` - Shows the leaderboard of the server.''')

        if interaction.user.guild_permissions.manage_guild:
            ephemeral = True
            emb.description += '''\n
**Restricted commands — Server Managers only**
`/set channel` - Sets the channel to chain words.
`/set failed_role` - Sets the role to give when a user fails.
`/set reliable_role` - Sets the reliable role.
`/unset failed_role` - Unsets the role to give when a user fails.
`/unset reliable_role` - Unset the reliable role.
`/blacklist add` - Add a word to the blacklist for this server.
`/blacklist remove` - Remove a word from the blacklist of this server.
`/blacklist show` - Show the blacklisted words for this server.
`/whitelist add` - Add a word to the whitelist for this server.
`/whitelist remove` - Remove a word from the whitelist of this server.
`/whitelist show` - Show the whitelist words for this server.'''

        if interaction.user.guild_permissions.administrator and interaction.guild.id == ADMIN_GUILD_ID:
            ephemeral = True
            emb.description += '''\n
**Restricted commands — Bot Admins only**
`/purge_data server` - Remove all data associated with a server.
`/purge_data user` - Remove all data associated with a user.
`/reload` - Reload a specific Cog (or all Cogs).'''

        await interaction.response.send_message(embed=emb, ephemeral=ephemeral)

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

        if not all(c in POSSIBLE_CHARACTERS for c in word.lower()):
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
                emb.description = f'✅ The word **{word}** is valid.'
                await interaction.followup.send(embed=emb)
                return

            if await self.bot.is_word_blacklisted(word, interaction.guild.id, connection):
                emb.description = f'❌ The word **{word}** is **blacklisted** and hence, **not** valid.'
                await interaction.followup.send(embed=emb)
                return

            if await self.bot.is_word_in_cache(word, connection):
                emb.description = f'✅ The word **{word}** is valid.'
                await interaction.followup.send(embed=emb)
                return

            future: concurrent.futures.Future = self.bot.start_api_query(word)

            match self.bot.get_query_response(future):
                case self.bot.API_RESPONSE_WORD_EXISTS:

                    emb.description = f'✅ The word **{word}** is valid.'

                    await self.bot.add_to_cache(word, connection)

                case self.bot.API_RESPONSE_WORD_DOESNT_EXIST:
                    emb.description = f'❌ **{word}** is **not** a valid word.'
                case _:
                    emb.description = f'⚠️ There was an issue in fetching the result.'

            await interaction.followup.send(embed=emb)

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
        async def server(self, interaction: Interaction):
            """Command to show the top 10 servers with the highest highscore"""
            await interaction.response.defer()

            emb = Embed(
                title=f'Top 10 servers by highscore',
                color=Colour.blue(),
                description=''
            ).set_author(name='Global')

            async with self.cog.bot.db_connection(locked=False) as connection:
                limit = 10

                stmt = (select(ServerConfigModel.server_id, ServerConfigModel.high_score)
                        .order_by(ServerConfigModel.high_score.desc())
                        .limit(limit))

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
        async def server(self, interaction: Interaction) -> None:
            """Command to show the stats of the server"""
            await interaction.response.defer()

            config: ServerConfig = self.cog.bot.server_configs[interaction.guild.id]

            if config.channel_id is None:  # channel not set yet
                await interaction.followup.send("Counting channel not set yet!")
                return

            server_stats_embed = Embed(
                description=f'''Current Chain Length: {config.current_count}
Longest chain length: {config.high_score}
{f"**Last word:** {config.current_word}" if config.current_word else ""}
{f"Last word by: <@{config.last_member_id}>" if config.last_member_id else ""}''',
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

