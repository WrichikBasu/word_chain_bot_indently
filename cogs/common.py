"""Cog that contains common logic and infrastructure."""
from __future__ import annotations

import logging
from logging.config import fileConfig
from typing import TYPE_CHECKING

import discord
from discord.ext import commands
from discord.ext.commands import Cog

from consts import LOGGER_NAME_COMMON_COG, COG_NAME_COMMON

if TYPE_CHECKING:
    from main import WordChainBot

fileConfig(fname='config.ini')
logger = logging.getLogger(LOGGER_NAME_COMMON_COG)


class CommonCog(Cog, name=COG_NAME_COMMON):

    def __init__(self, bot: WordChainBot):
        self.bot: WordChainBot = bot

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

    # ---------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    # ---------------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        pass

# ====================================================================================================================


async def setup(bot: WordChainBot):
    await bot.add_cog(CommonCog(bot))
