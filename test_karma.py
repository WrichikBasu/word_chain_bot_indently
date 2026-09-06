import math
from collections import deque

import pytest

from karma import calculate_total_karma

LIST_LENGTH = 5


@pytest.fixture
def empty_history():
    return deque(maxlen=LIST_LENGTH)


@pytest.fixture
def positive_scoring_words():
    return ['ad', 'arctic', 'app', 'aluminium', 'arena']


@pytest.fixture
def negative_scoring_words():
    return ['any', 'allow', 'mix', 'blitz', 'bank']


@pytest.fixture
def mixed_scoring_words():
    return ['age', 'armament', 'wish', 'finder', 'colab']


@pytest.fixture
def same_ending_letter_words():
    return ['as', 'souls', 'picks', 'clicks', 'mountains']


@pytest.fixture
def positive_score_history(positive_scoring_words: list[str]):
    last_words = deque(maxlen=LIST_LENGTH)
    for word in positive_scoring_words:
        last_words.append(word)
    return last_words


@pytest.fixture
def negative_score_history(negative_scoring_words: list[str]):
    last_words = deque(maxlen=LIST_LENGTH)
    for word in negative_scoring_words:
        last_words.append(word)
    return last_words


@pytest.fixture
def mixed_score_history(mixed_scoring_words: list[str]):
    last_words = deque(maxlen=LIST_LENGTH)
    for word in mixed_scoring_words:
        last_words.append(word)
    return last_words


@pytest.fixture
def same_ending_letter_history(same_ending_letter_words: list[str]):
    last_words = deque(maxlen=LIST_LENGTH)
    for word in same_ending_letter_words:
        last_words.append(word)
    return last_words


def test_precondition(positive_scoring_words: list[str], negative_scoring_words: list[str],
                      mixed_scoring_words: list[str], same_ending_letter_words: list[str]):
    for word in positive_scoring_words:
        assert calculate_total_karma(word, deque()) > 0
    for word in negative_scoring_words:
        assert calculate_total_karma(word, deque()) < 0
    for word in mixed_scoring_words:
        assert (word[-1:] not in [w[-1:] for w in positive_scoring_words] + [w[-1:] for w in negative_scoring_words] +
                [w[-1:] for w in same_ending_letter_words])
    for word in same_ending_letter_words:
        assert (word[-1:] not in [w[-1:] for w in positive_scoring_words] + [w[-1:] for w in negative_scoring_words] +
                [w[-1:] for w in mixed_scoring_words])


def test_positive_score_on_unused(positive_scoring_words: list[str], mixed_score_history: deque[str]):
    # positive scoring words will result in positive karma, if their ending letter has not been used recently
    for word in positive_scoring_words:
        assert word not in mixed_score_history
        karma = calculate_total_karma(word, mixed_score_history)
        mixed_score_history.append(word)
        assert karma > 0


def test_reduced_score_on_already_used(positive_scoring_words: list[str],
                                       positive_score_history: deque[str],
                                       negative_score_history: deque[str]):
    # positive scoring words will result in lower karma, if words with the same ending letter have been used recently
    for word in positive_scoring_words:
        assert word in positive_score_history
        karma_on_positive_history = calculate_total_karma(word, positive_score_history)
        karma_on_negative_history = calculate_total_karma(word, negative_score_history)
        positive_score_history.append(word)
        negative_score_history.append(word)
        assert karma_on_positive_history > 0
        assert karma_on_positive_history < karma_on_negative_history


def test_negative_score_irrelevant_history(negative_scoring_words: list[str],
                                           negative_score_history: deque[str],
                                           positive_score_history: deque[str]):
    # if base karma is negative, we do not apply decay based on history
    for word in negative_scoring_words:
        assert word in negative_score_history
        assert word not in positive_score_history
        karma_on_negative_history = calculate_total_karma(word, negative_score_history)
        karma_on_positive_history = calculate_total_karma(word, positive_score_history)
        negative_score_history.append(word)
        positive_score_history.append(word)
        assert karma_on_negative_history == karma_on_positive_history


def test_decrease_on_same_ending_letter(same_ending_letter_words: list[str], empty_history: deque[str]):
    # NOTE: value decreases as long as the list length limit is not reached
    last_karma = math.inf
    for word in same_ending_letter_words:
        karma = calculate_total_karma(word, empty_history)
        assert karma < last_karma
        last_karma = karma
        empty_history.append(word)
