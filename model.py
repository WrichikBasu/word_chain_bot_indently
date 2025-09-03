from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, List

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Float, Integer, String, update
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from consts import GameMode, Languages

if TYPE_CHECKING:
    from main import WordChainBot  # Thanks to https://stackoverflow.com/a/39757388/8387076


# ******************************************************************************************************************
# SQLAlchemy Models
# ******************************************************************************************************************

class Base(DeclarativeBase):
    pass


class ServerConfigModel(Base):

    __tablename__ = 'server_config'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[Optional[int]] = mapped_column(Integer)
    current_count: Mapped[int] = mapped_column(Integer)
    current_word: Mapped[Optional[str]] = mapped_column(String)
    high_score: Mapped[int] = mapped_column(Integer)
    used_high_score_emoji: Mapped[bool] = mapped_column(Boolean)
    last_member_id: Mapped[Optional[int]] = mapped_column(Integer)
    hard_mode_channel_id: Mapped[Optional[int]] = mapped_column(Integer)
    hard_mode_current_count: Mapped[int] = mapped_column(Integer)
    hard_mode_current_word: Mapped[Optional[str]] = mapped_column(String)
    hard_mode_high_score: Mapped[int] = mapped_column(Integer)
    hard_mode_used_high_score_emoji: Mapped[bool] = mapped_column(Boolean)
    hard_mode_last_member_id: Mapped[Optional[int]] = mapped_column(Integer)
    reliable_role_id: Mapped[Optional[int]] = mapped_column(Integer)
    failed_role_id: Mapped[Optional[int]] = mapped_column(Integer)
    failed_member_id: Mapped[Optional[int]] = mapped_column(Integer)
    correct_inputs_by_failed_member: Mapped[int] = mapped_column(Integer)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    languages: Mapped[str] = mapped_column(String, default='en')


class WordCacheModel(Base):
    __tablename__ = 'word_cache'
    word: Mapped[str] = mapped_column(String, primary_key=True)
    language: Mapped[str] = mapped_column(String, default='en')


class UsedWordsModel(Base):
    __tablename__ = 'used_words'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_mode: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class MemberModel(Base):
    __tablename__ = 'member'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    wrong: Mapped[int] = mapped_column(Integer)
    karma: Mapped[float] = mapped_column(Float)


class BlacklistModel(Base):
    __tablename__ = 'blacklist'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class WhitelistModel(Base):
    __tablename__ = 'whitelist'
    server_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String, primary_key=True)


class BannedMemberModel(Base):
    __tablename__ = 'banned_member'
    member_id: Mapped[int] = mapped_column(Integer, primary_key=True)

# ********************************************************************************************************************
# PYDANTIC MODELS
# ********************************************************************************************************************


class GameModeState(BaseModel):
    channel_id: Optional[int] = None
    current_count: int = 0
    current_word: Optional[str] = None
    high_score: int = 0
    used_high_score_emoji: bool = False
    last_member_id: Optional[int] = None


class ServerConfig(BaseModel):

    server_id: int
    game_state: dict[GameMode, GameModeState] = Field(default_factory=lambda: {
        GameMode.NORMAL: GameModeState(),
        GameMode.HARD: GameModeState()
    })
    reliable_role_id: Optional[int] = None
    failed_role_id: Optional[int] = None
    failed_member_id: Optional[int] = None
    correct_inputs_by_failed_member: int = 0
    is_banned: bool = False
    languages: List[Languages] = Field(default_factory=lambda: [Languages.ENGLISH])

    def fail_chain(self, game_mode: GameMode, member_id: int) -> None:
        """
        Resets the stats because a mistake was made.
        """
        self.game_state[game_mode].current_count = 0
        self.failed_member_id = member_id
        self.correct_inputs_by_failed_member = 0
        self.game_state[game_mode].used_high_score_emoji = False

    def update_current(self, game_mode: GameMode, member_id: int, current_word: str) -> None:
        """
        Increment the current count.
        """
        # increment current count
        self.game_state[game_mode].current_count += 1
        self.game_state[game_mode].current_word = current_word

        # update current member id
        self.game_state[game_mode].last_member_id = member_id

        # check the high score
        self.game_state[game_mode].high_score = max(self.game_state[game_mode].high_score, self.game_state[game_mode].current_count)

    def reaction_emoji(self, game_mode: GameMode) -> str:
        """
        Get the reaction emoji based on the current count.
        """
        special_emojis = {
            100: "💯",
            69: "😏",
            666: "👹",
        }
        if self.game_state[game_mode].current_count == self.game_state[game_mode].high_score:
            if not self.game_state[game_mode].used_high_score_emoji:
                emoji = "🎉"
                self.game_state[game_mode].used_high_score_emoji = True
            else:
                emoji = special_emojis.get(self.game_state[game_mode].current_count, '☑️')
        else:
            emoji = special_emojis.get(self.game_state[game_mode].current_count, '✅')
        return emoji

    def __update_statement(self):
        stmt = update(ServerConfigModel).values(
            channel_id=self.game_state[GameMode.NORMAL].channel_id,
            current_count=self.game_state[GameMode.NORMAL].current_count,
            current_word=self.game_state[GameMode.NORMAL].current_word,
            high_score=self.game_state[GameMode.NORMAL].high_score,
            used_high_score_emoji=self.game_state[GameMode.NORMAL].used_high_score_emoji,
            last_member_id=self.game_state[GameMode.NORMAL].last_member_id,
            hard_mode_channel_id=self.game_state[GameMode.HARD].channel_id,
            hard_mode_current_count=self.game_state[GameMode.HARD].current_count,
            hard_mode_current_word=self.game_state[GameMode.HARD].current_word,
            hard_mode_high_score=self.game_state[GameMode.HARD].high_score,
            hard_mode_used_high_score_emoji=self.game_state[GameMode.HARD].used_high_score_emoji,
            hard_mode_last_member_id=self.game_state[GameMode.HARD].last_member_id,
            reliable_role_id=self.reliable_role_id,
            failed_role_id=self.failed_role_id,
            failed_member_id=self.failed_member_id,
            correct_inputs_by_failed_member=self.correct_inputs_by_failed_member,
            is_banned=self.is_banned,
            languages=','.join(language.value for language in self.languages)
        ).where(ServerConfigModel.server_id == self.server_id)
        return stmt

    @staticmethod
    def from_sqlalchemy_row(row: Row) -> ServerConfig:
        """
        Converts a row from SQLAlchemy into an instance of ServerConfig. Replaces `model_validate` from Pydantic, which
        does not work anymore with the differences in structure in the Pydantic and SQLAlchemy models.
        :param row: row from SQLAlchemy
        :return: ServerConfig object
        """
        game_state = {
            GameMode.NORMAL: GameModeState(
                channel_id=row.channel_id,
                current_count=row.current_count,
                current_word=row.current_word,
                high_score=row.high_score,
                used_high_score_emoji=row.used_high_score_emoji,
                last_member_id=row.last_member_id
            ),
            GameMode.HARD: GameModeState(
                channel_id=row.hard_mode_channel_id,
                current_count=row.hard_mode_current_count,
                current_word=row.hard_mode_current_word,
                high_score=row.hard_mode_high_score,
                used_high_score_emoji=row.hard_mode_used_high_score_emoji,
                last_member_id=row.hard_mode_last_member_id
            )
        }

        return ServerConfig(
            server_id=row.server_id,
            game_state=game_state,
            reliable_role_id=row.reliable_role_id,
            failed_role_id=row.failed_role_id,
            failed_member_id=row.failed_member_id,
            correct_inputs_by_failed_member=row.correct_inputs_by_failed_member,
            is_banned=row.is_banned,
            languages=[Languages(lang_code) for lang_code in row.languages.split(',') if lang_code]
        )

    def to_sqlalchemy_dict(self) -> dict[str, Any]:
        """
        Converts an instance of ServerConfig into a dict compatible with the SQLAlchemy representation. Replaces
        `model_dump` from Pydantic, which does not work anymore with the differences in structure in the Pydantic and
        SQLAlchemy models.
        :return:
        """
        return {
            "server_id": self.server_id,
            "channel_id": self.game_state[GameMode.NORMAL].channel_id,
            "current_count": self.game_state[GameMode.NORMAL].current_count,
            "current_word": self.game_state[GameMode.NORMAL].current_word,
            "high_score": self.game_state[GameMode.NORMAL].high_score,
            "used_high_score_emoji": self.game_state[GameMode.NORMAL].used_high_score_emoji,
            "last_member_id": self.game_state[GameMode.NORMAL].last_member_id,
            "hard_mode_channel_id": self.game_state[GameMode.HARD].channel_id,
            "hard_mode_current_count": self.game_state[GameMode.HARD].current_count,
            "hard_mode_current_word": self.game_state[GameMode.HARD].current_word,
            "hard_mode_high_score": self.game_state[GameMode.HARD].high_score,
            "hard_mode_used_high_score_emoji": self.game_state[GameMode.HARD].used_high_score_emoji,
            "hard_mode_last_member_id": self.game_state[GameMode.HARD].last_member_id,
            "reliable_role_id": self.reliable_role_id,
            "failed_role_id": self.failed_role_id,
            "failed_member_id": self.failed_member_id,
            "correct_inputs_by_failed_member": self.correct_inputs_by_failed_member,
            "is_banned": self.is_banned,
            "languages": ','.join([language.value for language in self.languages])
        }

    async def sync_to_db(self, bot: WordChainBot):
        """
        Synchronizes itself with the DB.
        """
        async with bot.db_connection(locked=True) as connection:
            stmt = self.__update_statement()
            await connection.execute(stmt)
            await connection.commit()

    async def sync_to_db_with_connection(self, connection: AsyncConnection) -> int:
        """
        Synchronizes itself with the DB using an existing connection without committing.
        """
        stmt = self.__update_statement()
        result = await connection.execute(stmt)
        return result.rowcount  # noqa: custom property with memoization which IDEs won't recognize as a property

    class Config:
        from_attributes = True


class Member(BaseModel):
    server_id: int
    member_id: int
    score: int
    correct: int
    wrong: int
    karma: float

    class Config:
        from_attributes = True
