from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, Float, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ServerConfigModel(Base):
    __tablename__ = 'server_config'
    server_id = Column(Integer, primary_key=True)
    channel_id = Column(Integer)
    current_count = Column(Integer, nullable=False)
    current_word = Column(String)
    high_score = Column(Integer, nullable=False)
    put_high_score_emoji = Column(Boolean, nullable=False)
    reliable_role_id = Column(Integer)
    failed_role_id = Column(Integer)
    last_member_id = Column(Integer)
    failed_member_id = Column(Integer)
    correct_inputs_by_failed_member = Column(Integer, nullable=False)

class WordCacheModel(Base):
    __tablename__ = 'word_cache'
    word = Column(String, primary_key=True)

class UsedWordsModel(Base):
    __tablename__ = 'used_words'
    server_id = Column(Integer, primary_key=True)
    word = Column(String, primary_key=True)

class MemberModel(Base):
    __tablename__ = 'member'
    server_id = Column(Integer, primary_key=True)
    member_id = Column(Integer, primary_key=True)
    score = Column(Integer, nullable=False)
    correct = Column(Integer, nullable=False)
    wrong = Column(Integer, nullable=False)
    karma = Column(Float, nullable=False)

class BlacklistModel(Base):
    __tablename__ = 'blacklist'
    server_id = Column(Integer, primary_key=True)
    word = Column(String, primary_key=True)

class WhitelistModel(Base):
    __tablename__ = 'whitelist'
    server_id = Column(Integer, primary_key=True)
    word = Column(String, primary_key=True)

class ServerConfig(BaseModel):
    server_id: int
    channel_id: Optional[int] = None
    current_count: int = 0
    current_word: Optional[str] = None
    high_score: int = 0
    put_high_score_emoji: bool = False
    reliable_role_id: Optional[int] = None
    failed_role_id: Optional[int] = None
    last_member_id: Optional[int] = None
    failed_member_id: Optional[int] = None
    correct_inputs_by_failed_member: int = 0

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
