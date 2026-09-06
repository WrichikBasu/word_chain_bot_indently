import string

import pytest

from consts import GameMode
from language import Language

### ENGLISH

@pytest.mark.parametrize('token', list(string.ascii_lowercase), ids=lambda c: f'token_{c}')
def test_en_normal_mode(token: str):
    language = Language.ENGLISH
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', [
    'en', 'an', 'es', 'ey', 'ow', 'um', 'ej'
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_valid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', [
    'nd', 'ng', 'ld', 'ds', 'ia'
], ids=lambda c: f'token_{c}')
def test_en_hard_mode_expect_invalid(token: str):
    language = Language.ENGLISH
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


### GERMAN

@pytest.mark.parametrize('token', list(string.ascii_lowercase) + ['ä', 'ö', 'ü'], ids=lambda c: f'token_{c}')
def test_de_normal_mode(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', ['ß'], ids=lambda c: f'token_{c}')
def test_de_normal_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', [
    'ic', 'ek', 'gn', 'ör', 'äs', 'äq', 'zö', 'äl', 'än', 'äh'
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_valid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', [
    'ng', 'nd', 'ss', 'ld', 'ia'
], ids=lambda c: f'token_{c}')
def test_de_hard_mode_expect_invalid(token: str):
    language = Language.GERMAN
    mode = GameMode.HARD

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


# HUNGARIAN

@pytest.mark.parametrize('token', [c for c in string.ascii_lowercase if c not in ['y', 'x']], ids=lambda c: f'token_{c}')
def test_hu_normal_mode(token: str):
    language = Language.HUNGARIAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', ['y', 'x'], ids=lambda c: f'token_{c}')
def test_hu_normal_mode_expect_invalid(token: str):
    language = Language.HUNGARIAN
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'


# POLISH

@pytest.mark.parametrize('token', [c for c in string.ascii_lowercase if c not in ['y', 'x']], ids=lambda c: f'token_{c}')
def test_pl_normal_mode(token: str):
    language = Language.POLISH
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] >= language.value.score_threshold[mode], f'failed for {token=}'


@pytest.mark.parametrize('token', ['y', 'x'], ids=lambda c: f'token_{c}')
def test_pl_normal_mode_expect_invalid(token: str):
    language = Language.POLISH
    mode = GameMode.NORMAL

    assert language.value.first_token_scores[mode][token] < language.value.score_threshold[mode], f'failed for {token=}'
