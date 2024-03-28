"""Word chain bot for the Indently server"""
import asyncio
import concurrent.futures
import json
import os
import sqlite3
import string
from dataclasses import dataclass
from typing import Optional, NoReturn
from requests_futures.sessions import FuturesSession
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv('.env')

TOKEN: str = os.getenv('TOKEN')
POSSIBLE_CHARACTERS: str = string.ascii_lowercase


@dataclass
class Config:
    """Configuration for the bot"""
    channel_id: Optional[int] = None
    current_count: int = 0
    current_word: Optional[str] = None
    high_score: int = 0
    current_member_id: Optional[int] = None
    put_high_score_emoji: bool = False
    failed_role_id: Optional[int] = None
    reliable_counter_role_id: Optional[int] = None
    failed_member_id: Optional[int] = None
    correct_inputs_by_failed_member: int = 0

    @staticmethod
    def read():
        _config: Optional[Config] = None
        try:
            with open("config.json", "r") as file:
                _config = Config(**json.load(file))
        except FileNotFoundError:
            _config = Config()
            _config.dump_data()
        return _config

    def dump_data(self) -> None:
        """Update the config.json file"""
        with open("config.json", "w", encoding='utf-8') as file:
            json.dump(self.__dict__, file, indent=2)

    def update_current(self, member_id: int, current_word: str) -> None:
        """
        Increment the current count.
        NOTE: config is no longer dumped by default. Explicitly call config.dump().
        """
        # increment current count
        self.current_count += 1
        self.current_word = current_word

        # update current member id
        self.current_member_id = member_id

        # check the high score
        self.high_score = max(self.high_score, self.current_count)

    def reset(self) -> None:
        """
        Reset chain stats.
        Do NOT reset the current word.
        NOTE: config is no longer dumped by default. Explicitly call config.dump_data().
        """
        self.current_count = 0
        self.correct_inputs_by_failed_member = 0

        # update current member id
        self.current_member_id = None
        self.put_high_score_emoji = False

    def reaction_emoji(self) -> str:
        """
        Get the reaction emoji based on the current count.
        NOTE: Data is no longer dumped automatically. Explicitly call config.data_dump().
        """
        if self.current_count == self.high_score and not self.put_high_score_emoji:
            emoji = "🎉"
            self.put_high_score_emoji = True  # Needs a config data dump
        elif self.current_count == 100:
            emoji = "💯"
        elif self.current_count == 69:
            emoji = "😏"
        elif self.current_count == 666:
            emoji = "👹"
        else:
            emoji = "✅"
        return emoji


class Bot(commands.Bot):
    """Counting Discord bot for Indently discord server."""

    TABLE_USED_WORDS: str = "used_words"
    TABLE_MEMBERS: str = "members"

    RESPONSE_WORD_EXISTS: int = 1
    RESPONSE_WORD_DOESNT_EXIST: int = 0
    RESPONSE_ERROR: int = -1

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self._config: Config = Config.read()
        self._busy: int = 0
        self.participating_users: Optional[set[int]] = None
        self.failed_role: Optional[discord.Role] = None
        self.reliable_role: Optional[discord.Role] = None
        super().__init__(command_prefix='!', intents=intents)

    def read_config(self):
        """
        Force re-reading the config from the json to the instance variable.
        Mostly for use by slash command functions after they have changed the config values.
        """
        self._config = Config.read()

    async def on_ready(self) -> None:
        """Override the on_ready method"""
        print(f'Bot is ready as {self.user.name}#{self.user.discriminator}')

        if self._config.channel_id is not None:
            channel = bot.get_channel(self._config.channel_id)

            if self._config.current_word and self._config.current_member_id:
                member: discord.Member = await channel.guild.fetch_member(self._config.current_member_id)
                await channel.send(
                    f'I\'m now online! Last word by {member.mention}. The **next** word should **begin** with '
                    f'the letter **{self._config.current_word[-1]}**.')
            else:
                await channel.send(f'I\'m now online!')

        self.set_roles()

    def set_roles(self):
        """
        Sets the `self.failed_role` and `self.reliable_counter_role` variables.
        """
        for member in self.get_all_members():
            guild: discord.Guild = member.guild

            # Set self.failed_role
            if self._config.failed_role_id is not None:
                self.failed_role = discord.utils.get(guild.roles, id=self._config.failed_role_id)
            else:
                self.failed_role = None

            # Set self.reliable_counter_role
            if self._config.reliable_counter_role_id is not None:
                self.reliable_role = discord.utils.get(guild.roles, id=self._config.reliable_counter_role_id)
            else:
                self.reliable_role = None

            break

    async def add_remove_reliable_role(self):
        """
        Adds/removes the reliable role from participating users.

        Criteria for getting the reliable role:
        1. Accuracy must be > 99%. (Accuracy = correct / (correct + wrong)).
        2. Must have >= 100 correct inputs.
        3. Must have score >= 100.
        """
        if self.reliable_role and self.participating_users:

            users: set[int] = self.participating_users.copy()  # Copy into a variable to prevent data anomaly
            self.participating_users = None

            conn: sqlite3.Connection = sqlite3.connect('database.sqlite3')
            cursor: sqlite3.Cursor = conn.cursor()

            for user_id in users:

                try:
                    member: discord.Member = await self.reliable_role.guild.fetch_member(user_id)
                    cursor.execute(f'SELECT correct, wrong, score FROM members WHERE member_id = {user_id} '
                                   f'AND server_id = {member.guild.id}')
                    stats: Optional[tuple[int]] = cursor.fetchone()

                    if stats:
                        accuracy: float = stats[0] / (stats[0] + stats[1])

                        if accuracy > 0.990 and stats[0] >= 100 and stats[2] >= 100:
                            await member.add_roles(self.reliable_role)
                        else:
                            await member.remove_roles(self.reliable_role)

                except discord.NotFound:
                    # Member no longer in the server
                    continue

    async def add_remove_failed_role(self):
        """
        Adds the `self.failed_role` to the user whose id is stored in `self._config.failed_member_id`.
        Removes the failed role from all other users.
        Does not proceed if failed role has not been set.
        If `self.failed_role` is not `None` but `self._config.failed_member_id` is `None`, then simply removes
        the failed role from all members who have it currently.
        """
        if self.failed_role:
            handled_member: bool = False

            for member in self.failed_role.members:
                # Iterate through members who have the failed role, and remove those who have not failed

                if self._config.failed_member_id and self._config.failed_member_id == member.id:
                    # Current failed member already has the failed role, so just continue
                    handled_member = True
                    continue
                else:
                    # Either failed_member_id is None, or this member is not the current failed member.
                    # In either case, we have to remove the role.
                    await member.remove_roles(self.failed_role)

            if not handled_member and self._config.failed_member_id:
                # Current failed member does not yet have the failed role
                try:
                    failed_member: discord.Member = await self.failed_role.guild.fetch_member(
                        self._config.failed_member_id)
                    await failed_member.add_roles(self.failed_role)
                except discord.NotFound:
                    # Member is no longer in the server
                    self._config.failed_member_id = None
                    self._config.correct_inputs_by_failed_member = 0
                    self._config.dump_data()

    async def schedule_busy_work(self):
        await asyncio.sleep(5)
        self._busy -= 1
        await self.do_busy_work()

    async def do_busy_work(self):
        if self._busy == 0:
            self._config.dump_data()
            await self.add_remove_failed_role()
            await self.add_remove_reliable_role()

    async def on_message(self, message: discord.Message) -> None:
        """Override the on_message method"""
        if message.author == self.user:
            return

        # Check if the message is in the channel
        if message.channel.id != self._config.channel_id:
            return

        word: str = message.content.lower()
        if not all(c in POSSIBLE_CHARACTERS for c in word):
            return

        self._busy += 1

        if self.participating_users is None:
            self.participating_users = {message.author.id, }
        else:
            self.participating_users.add(message.author.id)

        conn = sqlite3.connect('database.sqlite3')
        c = conn.cursor()
        c.execute(f'SELECT highest_valid_count FROM members WHERE member_id = {message.author.id} '
                  f'AND server_id = {message.guild.id}')
        stats: Optional[tuple[int]] = c.fetchone()

        if stats is None:
            highest_valid_count = 0
            c.execute(f'INSERT INTO members VALUES({message.guild.id}, {message.author.id}, 0, 0, 0, 0)')
            conn.commit()
        else:
            highest_valid_count = stats[0]

        # --------------------------
        # Check if word is valid
        # --------------------------
        # Start the API request, but deal with it later
        future: concurrent.futures.Future = self.start_api_query(word)

        # -------------------------
        # Wrong starting letter
        # -------------------------
        if self._config.current_word and word[0] != self._config.current_word[-1]:
            response: str = f'''{message.author.mention} messed up the chain! \
The word you entered did not begin with the last letter of the previous word ({self._config.current_word[-1]}).
Restart with a word starting with **{self._config.current_word[-1]}** and try to beat the \
current high score of **{self._config.high_score}**!'''

            await self.handle_mistake(message, response, conn)

            return

        # -------------
        # Wrong member
        # -------------
        if self._config.current_word and self._config.current_member_id == message.author.id:
            response: str = f'''{message.author.mention} messed up the count! \
You cannot send two words in a row!
Restart with a word starting with **{self._config.current_word[-1]}** and \
try to beat the current high score of **{self._config.high_score}**!'''

            await self.handle_mistake(message=message, response=response, conn=conn)

            return

        # --------------------
        # Check repetitions
        # (Repetitions are not mistakes)
        # --------------------
        c.execute(f'SELECT words FROM {Bot.TABLE_USED_WORDS} WHERE server_id = {message.guild.id} AND words = "{word}"')
        used_words = c.fetchone()
        if used_words is not None:
            await message.channel.send(f'''The word {word} has already been used before. \
The chain has **not** been broken.
Please enter another word.''')
            await message.add_reaction('❌')
            await self.schedule_busy_work()
            return

        # ----------------------------------
        # Check if word is valid (contd.)
        # ----------------------------------
        result: int = self.get_query_response(future)

        if result == Bot.RESPONSE_WORD_DOESNT_EXIST:

            if self._config.current_word:
                response: str = f'''{message.author.mention} messed up the chain! \
The word you entered does not exist.
Restart with a word starting with **{self._config.current_word[-1]}** and try to beat the \
current high score of **{self._config.high_score}**!'''
            else:
                response: str = f'''{message.author.mention} messed up the chain! \
The word you entered does not exist.
Restart and try to beat the current high score of **{self._config.high_score}**!'''

            await self.handle_mistake(message=message, response=response, conn=conn)
            return

        elif result == Bot.RESPONSE_ERROR:

            await message.add_reaction('⚠️')
            await message.channel.send(''':stop_sign: There was an issue in the backend.
The above entered word is **NOT** being taken into account.''')

            await self.schedule_busy_work()
            return

        # --------------------
        # Everything is fine
        # ---------------------
        current_count = self._config.current_count + 1
        self._config.update_current(message.author.id, current_word=word)  # config dump triggered at the end of the method

        await message.add_reaction(self._config.reaction_emoji())  # config dumping done at the end of the method

        c.execute(f'''UPDATE members SET score = score + 1,
correct = correct + 1
{f", highest_valid_count  = {current_count}" if current_count > highest_valid_count else ""}
WHERE member_id = ? AND server_id = ?''',
                  (message.author.id, message.guild.id))
        c.execute(f'INSERT INTO {Bot.TABLE_USED_WORDS} VALUES ({message.guild.id}, "{word}")')
        conn.commit()
        conn.close()

        # Check and reset the self._config.failed_member_id to None.
        # No need to remove the role itself, it will be done later when not busy
        if self.failed_role and self._config.failed_member_id == message.author.id:
            self._config.correct_inputs_by_failed_member += 1
            if self._config.correct_inputs_by_failed_member >= 30:
                self._config.failed_member_id = None
                self._config.correct_inputs_by_failed_member = 0

        await self.schedule_busy_work()

    # ---------------------------------------------------------------------------------------

    async def handle_mistake(self, message: discord.Message,
                             response: str, conn: sqlite3.Connection) -> None:
        """Handles when someone messes up the count with a wrong number"""

        if self.failed_role:
            self._config.failed_member_id = message.author.id  # Designate current user as failed member
            # Adding/removing failed role is done when not busy

        self._config.reset()  # config dump is triggered at the end of if-statement

        await message.channel.send(response)
        await message.add_reaction('❌')

        c = conn.cursor()
        c.execute(f'UPDATE members '
                  f'SET score = score - 1, wrong = wrong + 1 '
                  f'WHERE member_id = {message.author.id} AND '
                  f'server_id = {message.guild.id}')
        # Clear used words schema
        c.execute(f'DELETE FROM {Bot.TABLE_USED_WORDS} WHERE server_id = {message.guild.id}')
        conn.commit()
        conn.close()

        await self.schedule_busy_work()

    # ------------------------------------------------------------------------------------------------
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
            `Bot.RESPONSE_WORD_EXISTS` is the word exists, `Bot.RESPONSE_WORD_DOESNT_EXIST` if the word does not exist,
            or `Bot.RESPONSE_ERROR` if an error (of any type) was raised in the query.
        """
        try:
            response = future.result(timeout=2)

            if response.status_code >= 400:
                print(f'Received response code {response.status_code}')
                return Bot.RESPONSE_ERROR

            data = response.json()
            print(data)

            word: str = data[0]
            best_match: str = data[1][0]  # Should raise an IndexError if no match is returned

            if best_match.lower() == word:
                return Bot.RESPONSE_WORD_EXISTS
            else:
                # Normally, the control should not reach this else statement.
                # If, however, some word is returned by chance, and it doesn't match the entered word,
                # this else will take care of it
                return Bot.RESPONSE_WORD_DOESNT_EXIST

        except TimeoutError:  # Send Bot.RESPONSE_ERROR
            print('Timeout error raised when trying to get the query result.')
        except IndexError:
            return Bot.RESPONSE_WORD_DOESNT_EXIST
        except Exception as ex:
            print(f'An exception was raised while getting the query result:\n{ex}')

        return Bot.RESPONSE_ERROR

    # ------------------------------------------------------------------------------------------------

    async def on_message_delete(self, message: discord.Message) -> None:
        """Post a message in the channel if a user deletes their input."""

        if not self.is_ready():
            return

        if message.author == self.user:
            return

        # Check if the message is in the channel
        if message.channel.id != self._config.channel_id:
            return
        if not message.reactions:
            return
        if not all(c in POSSIBLE_CHARACTERS for c in message.content):
            return
        # TODO
        await message.channel.send(
            f'{message.author.mention} deleted their word!  '
            f'The **last** word was **{self._config.current_word}**.')

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Send a message in the channel if a user modifies their input."""

        if not self.is_ready():
            return

        if before.author == self.user:
            return

        # Check if the message is in the channel
        if before.channel.id != self._config.channel_id:
            return
        if not before.reactions:
            return
        if not all(c in POSSIBLE_CHARACTERS for c in before.content):
            return
        if before.content == after.content:
            return
        # TODO
        await after.channel.send(
            f'{after.author.mention} edited their word! The **last** word was **{self._config.current_word}**.')

    async def setup_hook(self) -> NoReturn:
        await self.tree.sync()
        conn = sqlite3.connect('database.sqlite3')
        c = conn.cursor()
        c.execute(f'CREATE TABLE IF NOT EXISTS {Bot.TABLE_MEMBERS} '
                  '(server_id INTEGER NOT NULL, '
                  'member_id INTEGER NOT NULL, '
                  'score INTEGER NOT NULL, '
                  'correct INTEGER NOT NULL, '
                  'wrong INTEGER NOT NULL, '
                  'highest_valid_count INTEGER NOT NULL, '
                  'PRIMARY KEY (server_id, member_id))')

        c.execute(f'CREATE TABLE IF NOT EXISTS {Bot.TABLE_USED_WORDS} '
                  f'(server_id INTEGER NOT NULL, '
                  'words VARCHAR(255) NOT NULL, '
                  'PRIMARY KEY (server_id, words))')
        conn.commit()
        conn.close()


bot = Bot()


@bot.tree.command(name='sync', description='Syncs the slash commands to the bot')
@app_commands.checks.has_permissions(administrator=True, ban_members=True)
async def sync(interaction: discord.Interaction):
    """Sync all the slash commands to the bot"""
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message('You do not have permission to do this!')
        return
    await interaction.response.defer()
    await bot.tree.sync()
    await interaction.followup.send('Synced!')


@bot.tree.command(name='set_channel', description='Sets the channel to count in')
@app_commands.describe(channel='The channel to count in')
@app_commands.checks.has_permissions(ban_members=True)
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """Command to set the channel to count in"""
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message('You do not have permission to do this!')
        return
    config = Config.read()
    config.channel_id = channel.id
    config.dump_data()
    bot.read_config()  # Explicitly ask the bot to re-read the config
    await interaction.response.send_message(f'Word chain channel was set to {channel.mention}')


@bot.tree.command(name='listcmds', description='Lists commands')
async def list_commands(interaction: discord.Interaction):
    """Command to list all the slash commands"""
    emb = discord.Embed(title='Slash Commands', color=discord.Color.blue(),
                        description='''
**sync** - Syncs the slash commands to the bot (Admins only)
**set_channel** - Sets the channel to count in (Admins only)
**listcmds** - Lists all the slash commands
**stats_user** - Shows the stats of a specific user
**stats_server** - Shows the stats of the server
**check_word** - Check if a word exists/check the spelling.
**leaderboard** - Shows the leaderboard of the server
**set_failed_role** - Sets the role to give when a user fails (Admins only)
**set_reliable_role** - Sets the role to give when a user passes the score of 100 (Admins only)
**remove_failed_role** - Removes the role to give when a user fails (Admins only)
**remove_reliable_role** - Removes the role to give when a user passes the score of 100 (Admins only)
**force_dump** - Forcibly dump bot config data. Use only when no one is actively playing. (Admins only)
**prune** - Remove data for users who are no longer in the server. (Admins only)''')
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name='stats_user', description='Shows the user stats')
@app_commands.describe(member='The member to get the stats for')
async def stats_user(interaction: discord.Interaction, member: discord.Member = None):
    """Command to show the stats of a specific user"""
    await interaction.response.defer()

    if member is None:
        member = interaction.user

    emb = discord.Embed(title=f'{member.display_name}\'s stats', color=discord.Color.blue())

    conn = sqlite3.connect('database.sqlite3')
    c = conn.cursor()

    c.execute(f'SELECT score, correct, wrong, highest_valid_count '
              f'FROM {Bot.TABLE_MEMBERS} WHERE member_id = {member.id} AND server_id = {member.guild.id}')
    stats = c.fetchone()

    if stats is None:
        await interaction.followup.send('You have never played in this server!')
        conn.close()
        return

    c.execute(f'SELECT COUNT(member_id) FROM members WHERE score >= {stats[0]} AND server_id = {member.guild.id}')
    position = c.fetchone()[0]
    conn.close()

    emb.description = f'''{member.mention}\'s stats:\n
**Score:** {stats[0]} (#{position})
**✅Correct:** {stats[1]}
**❌Wrong:** {stats[2]}
**Highest valid count:** {stats[3]}\n
**Accuracy:** {(stats[1] / (stats[1] + stats[2])) * 100:.2f}%'''

    await interaction.followup.send(embed=emb)


@bot.tree.command(name="stats_server", description="View server word chain stats")
async def stats_server(interaction: discord.Interaction):
    """Command to show the stats of the server"""
    # Use the bot's config variable, do not re-read file as it may not have been updated yet
    config: Config = bot._config

    if config.channel_id is None:  # channel not set yet
        await interaction.response.send_message("Counting channel not set yet!")
        return

    server_stats_embed = discord.Embed(
        description=f'''Current Chain Length: {config.current_count}
Longest chain length: {config.high_score}
{f"**Last word:** {config.current_word}" if config.current_word else ""}
{f"Last word by: <@{config.current_member_id}>" if config.current_member_id else ""}''',
        color=discord.Color.blurple()
    )
    server_stats_embed.set_author(name=interaction.guild, icon_url=interaction.guild.icon)

    await interaction.response.send_message(embed=server_stats_embed)


@bot.tree.command(name='leaderboard', description='Shows the first 10 users with the highest score')
async def leaderboard(interaction: discord.Interaction):
    """Command to show the top 10 users with the highest score in Indently"""
    await interaction.response.defer()
    emb = discord.Embed(title='Top 10 users in Indently',
                        color=discord.Color.blue(), description='')

    conn = sqlite3.connect('database.sqlite3')
    c = conn.cursor()
    c.execute(f'SELECT member_id, score FROM members WHERE server_id = {interaction.guild.id} '
              f'ORDER BY score DESC LIMIT 10')
    users = c.fetchall()

    for i, user in enumerate(users, 1):
        user_obj = await interaction.guild.fetch_member(user[0])
        emb.description += f'{i}. {user_obj.mention} **{user[1]}**\n'
    conn.close()

    await interaction.followup.send(embed=emb)


@bot.tree.command(name='check_word', description='Check if a word is correct')
@app_commands.describe(word='The word to check')
async def check_word(interaction: discord.Interaction, word: str):

    future: concurrent.futures.Future = Bot.start_api_query(word)

    await interaction.response.defer()

    emb = discord.Embed(title=f'Check if word exists', color=discord.Color.gold())

    match Bot.get_query_response(future):
        case Bot.RESPONSE_WORD_EXISTS:
            emb.description = f':white_check_mark: The word "*{word}*\" exists.'
        case Bot.RESPONSE_WORD_DOESNT_EXIST:
            emb.description = f':x: The word \"*{word}*\" does **not** exist.'
        case _:
            emb.description = f':warning: There was an issue in fetching the result.'

    await interaction.followup.send(embed=emb)


@bot.tree.command(name='set_failed_role',
                  description='Sets the role to be used when a user puts a wrong word')
@app_commands.describe(role='The role to be used when a user puts a wrong word')
@app_commands.default_permissions(ban_members=True)
async def set_failed_role(interaction: discord.Interaction, role: discord.Role):
    """Command to set the role to be used when a user fails to count"""
    config = Config.read()
    config.failed_role_id = role.id
    config.dump_data()
    bot.read_config()  # Explicitly ask the bot to re-read the config
    bot.set_roles()  # Ask the bot to re-load the roles
    await interaction.response.send_message(f'Failed role was set to {role.mention}')


@bot.tree.command(name='set_reliable_role',
                  description='Sets the role to be used when a user attains a score of 100')
@app_commands.describe(role='The role to be used when a user attains a score of 100')
@app_commands.default_permissions(ban_members=True)
async def set_reliable_role(interaction: discord.Interaction, role: discord.Role):
    """Command to set the role to be used when a user gets 100 of score"""
    config = Config.read()
    config.reliable_counter_role_id = role.id
    config.dump_data()
    bot.read_config()  # Explicitly ask the bot to re-read the config
    bot.set_roles()  # Ask the bot to re-load the roles
    await interaction.response.send_message(f'Reliable role was set to {role.mention}')


@bot.tree.command(name='remove_failed_role', description='Removes the failed role feature')
@app_commands.default_permissions(ban_members=True)
async def remove_failed_role(interaction: discord.Interaction):
    config = Config.read()
    config.failed_role_id = None
    config.failed_member_id = None
    config.correct_inputs_by_failed_member = 0
    config.dump_data()
    bot.read_config()  # Explicitly ask the bot to re-read the config
    bot.set_roles()  # Ask the bot to re-load the roles
    await interaction.response.send_message('Failed role removed')


@bot.tree.command(name='remove_reliable_role', description='Removes the reliable role feature')
@app_commands.default_permissions(ban_members=True)
async def remove_reliable_role(interaction: discord.Interaction):
    config = Config.read()
    config.reliable_counter_role_id = None
    config.dump_data()
    bot.read_config()  # Explicitly ask the bot to re-read the config
    bot.set_roles()  # Ask the bot to re-load the roles
    await interaction.response.send_message('Reliable role removed')


@bot.tree.command(name='disconnect', description='Makes the bot go offline')
@app_commands.default_permissions(ban_members=True)
async def disconnect(interaction: discord.Interaction):
    config = Config.read()
    if config.channel_id is not None:
        channel = bot.get_channel(config.channel_id)
        await channel.send('Bot is now offline.')
    await bot.close()


@bot.tree.command(name='force_dump', description='Forcibly dumps configuration data')
@app_commands.default_permissions(ban_members=True)
async def force_dump(interaction: discord.Interaction):
    bot._busy = 0
    await bot.do_busy_work()
    await interaction.response.send_message('Configuration data successfully dumped.')


@bot.tree.command(name='prune', description='(DANGER) Deletes data of users who are no longer in the server')
@app_commands.default_permissions(ban_members=True)
async def prune(interaction: discord.Interaction):
    await interaction.response.defer()

    conn: sqlite3.Connection = sqlite3.connect('database.sqlite3')
    cursor: sqlite3.Cursor = conn.cursor()

    cursor.execute(f'SELECT member_id FROM {Bot.TABLE_MEMBERS} WHERE server_id = {interaction.guild.id}')
    result: Optional[list[tuple[int]]] = cursor.fetchall()

    if result:
        count: int = 0

        for res in result:
            user_id: int = res[0]

            if interaction.guild.get_member(user_id) is None:
                cursor.execute(f'DELETE FROM members WHERE member_id = {user_id} '
                               f'AND server_id = {interaction.guild.id}')
                count += 1
                print(f'Removed data for user {user_id}.')

        if count > 0:
            conn.commit()
            await interaction.followup.send(f'Successfully removed data for {count} user(s).')
        else:
            await interaction.followup.send('No users met the criteria to be removed.')

    else:
        await interaction.followup.send('No users found in the database.')

    conn.close()


if __name__ == '__main__':
    bot.run(TOKEN)
