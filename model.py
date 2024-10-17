from pydantic import BaseModel
from sqlalchemy import REAL, TEXT, Column, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class WordCacheModel(Base):
    __tablename__ = 'word_cache'
    words = Column(TEXT, primary_key=True)

class UsedWordsModel(Base):
    __tablename__ = 'used_words'
    server_id = Column(Integer, primary_key=True)
    words = Column(TEXT, primary_key=True)

class MemberModel(Base):
    __tablename__ = 'members'
    server_id = Column(Integer, primary_key=True)
    member_id = Column(Integer, primary_key=True)
    score = Column(Integer, nullable=False)
    correct = Column(Integer, nullable=False)
    wrong = Column(Integer, nullable=False)
    karma = Column(REAL, nullable=False)

class BlacklistModel(Base):
    __tablename__ = 'blacklist'
    server_id = Column(Integer, primary_key=True)
    words = Column(TEXT, primary_key=True)

class WhitelistModel(Base):
    __tablename__ = 'whitelist'
    server_id = Column(Integer, primary_key=True)
    words = Column(TEXT, primary_key=True)

class Member(BaseModel):
    server_id: int
    member_id: int
    score: int
    correct: int
    wrong: int
    karma: float

    class Config:
        from_attributes = True
