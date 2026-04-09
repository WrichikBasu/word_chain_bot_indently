"""Cog that contains the actual game logic."""
from __future__ import annotations

import logging
from logging.config import fileConfig
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.ext.commands import Cog

from consts import COG_NAME_GAME, LOGGER_NAME_GAME_COG

if TYPE_CHECKING:
    from main import WordChainBot

fileConfig(fname='config.ini')
logger = logging.getLogger(LOGGER_NAME_GAME_COG)


class GameCog(Cog, name=COG_NAME_GAME):

    def __init__(self, bot: WordChainBot):
        super().__init__()
        self.bot = bot

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
    async def on_ready(self) -> None:
        logger.info(f'game cog ready')

    # ----------------------------------------------------------------------------------------------------------------
    
    @commands.Cog.listener()
    async def on_guild_join(self) -> None:
        pass

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        pass

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        pass

    # ----------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        pass

# ====================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(GameCog(bot))
