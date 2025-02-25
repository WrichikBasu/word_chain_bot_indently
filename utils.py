"""
A place to consolidate all utility methods that can be made `static` if included in a class.

Place static methods here to avoid cyclic imports.
"""
from __future__ import annotations
import contextlib
import logging
import math
import time
from collections import deque
from typing import AsyncIterator, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncConnection

from consts import FIRST_CHAR_SCORE

if TYPE_CHECKING:
    from main import WordChainBot  # Thanks to https://stackoverflow.com/a/39757388/8387076


def calculate_decay(n: float, drop_rate: float = .33) -> float:
    """
    Calculates a decay factor based on an occurrence score of same letter ending words in history.

    Parameters
    ----------
    n : float
        Positive score of occurrences in history.
    drop_rate : float
        Positive rate of change to approach the lower boundary.

    Returns
    -------
    float
        A decay factor between 1 and -1 that can be multiplied with the karma.
    """
    return (2 * math.e ** (-n * drop_rate)) - 1

# ==================================================================================================================


def calculate_base_karma(word: str, last_char_bias: float = .7) -> float:
    """
    Calculates the base karma gain or loss for given word.

    Parameters
    ----------
    word : str
        The word to calculate the karma change from.
    last_char_bias : float
        Bias to be multiplied with the karma part for the last character.

    Returns
    -------
    float
        The change in karma, usually closely around 0.
    """

    def score_adaption(score: float, exponent: float = .5, rise: float = .025) -> float:
        return score ** exponent + rise

    first_char_score: float = score_adaption(FIRST_CHAR_SCORE[word[0]])  # how difficult is it to find this word
    last_char_score: float = score_adaption(FIRST_CHAR_SCORE[word[-1]])  # how difficult is it for the next player

    first_char_karma: float = (first_char_score - 1) * -1  # distance to average, inverted
    last_char_karma: float = (last_char_score - 1)  # distance to average

    # no karma loss if first char is common, because you cannot choose the first one, it is determined by last one
    # apply bias to last characters karma to fine tune the total influence
    return (first_char_karma if first_char_karma > 0 else 0) + (last_char_karma * last_char_bias)

# ==================================================================================================================


def calculate_total_karma(word: str, last_words: deque[str]) -> float:
    """
    Calculates the total karma gain or loss for given word and history.

    Parameters
    ----------
    word : str
        The word to calculate the karma change from.
    last_words : deque[str]
        The history to include in the karma calculation.

    Returns
    -------
    float
        The total change in karma, usually closely around 0.
    """
    end_letter: str = word[-1]
    weighted_words: list[tuple[float, str]] = [(2 * (len(last_words) - index) / len(last_words), e) for index, e in
                                               enumerate(last_words)]
    n: float = sum(weight for weight, e in weighted_words if e[-1] == end_letter)

    decay: float = calculate_decay(n)
    base_karma: float = calculate_base_karma(word)
    return decay * base_karma if base_karma > 0 else base_karma

# =================================================================================================================


@contextlib.asynccontextmanager
async def db_connection(bot: WordChainBot, locked: bool = True) -> AsyncIterator[AsyncConnection]:
    """
    Creates a connection to the database.

    Parameters
    ----------
    bot : WordChainBot
        Instance of the main bot.
    locked : bool
        Whether to lock the DB or not.

    Yields
    ------
    AsyncIterator[AsyncConnection]
        The connection to the database.
    """
    logger = logging.getLogger(__name__)
    logger.debug(f'requesting connection with {locked=}')

    if locked:
        start_time = time.monotonic()
        async with bot._LOCK:
            wait_time = time.monotonic() - start_time
            logger.debug(f'Waited {wait_time:.4f} seconds for DB lock')
            async with bot._SQL_ENGINE.begin() as connection:
                yield connection
    else:
        async with bot._SQL_ENGINE.begin() as connection:
            yield connection

    logger.debug(f'connection done')

