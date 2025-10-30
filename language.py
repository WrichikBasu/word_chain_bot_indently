import json
import logging
import os.path
from collections import defaultdict
from enum import Enum
from json import JSONDecodeError
from os import PathLike
from pathlib import Path

from pydantic import BaseModel, Field

from consts import GameMode

logger = logging.getLogger(__name__)


def build_regex(start_group: str, middle_group: str, end_group: str) -> str:
    return rf'^({start_group})({middle_group})*({end_group})$'


EN_REGEX: str = build_regex('[a-z]', '[-]|[a-z]', '[a-z]')
FR_REGEX: str = build_regex('[a-zàâæçéèêëîïôœùûüÿ]', '[-]|[a-zàâæçéèêëîïôœùûüÿ]', '[a-zàâæçéèêëîïôœùûüÿ]')
DE_REGEX: str = build_regex('[a-zäöü]', '[-]|[a-zäöüß]', '[a-zäöüß]')
NL_REGEX: str = build_regex('[a-zéèëç]', '[-]|[a-zéèëç]', '[a-zéèëç]')
ES_REGEX: str = build_regex('[a-záéíóúüñ]', '[-]|[a-záéíóúüñ]', '[a-záéíóúüñ]')
PT_REGEX: str = build_regex('[a-záâãàçéêíóôõú]', '[-]|[a-záâãàçéêíóôõú]', '[a-záâãàçéêíóôõú]')
IT_REGEX: str = build_regex('[a-zàèéìíîòóùú]', '[-]|[a-zàèéìíîòóùú]', '[a-zàèéìíîòóùú]')
NN_REGEX: str = build_regex('[a-zæøå]', '[-]|[a-zæøå]', '[a-zæøå]')  # north germanic (danish, norwegian)
SV_REGEX: str = build_regex('[a-zåäö]', '[a-zåäö]', '[a-zåäö]')
IS_REGEX: str = build_regex('[a-záéíóúýþæö]', '[-]|[a-záéíóúýþæöð]', '[a-záéíóúýþæöð]')  # icelandic and faroese
PL_REGEX: str = build_regex('[a-ząćęłńóśźż]', '[-]|[a-ząćęłńóśźż]', '[a-ząćęłńóśźż]')
CS_REGEX: str = build_regex('[a-záčďéěíňóřšťůýž]', '[-]|[a-záčďéěíňóřšťůýž]', '[a-záčďéěíňóřšťůýž]')  # czech and slovak
SS_REGEX: str = build_regex('[a-zčćđšž]', '[-]|[a-zčćđšž]','[a-zčćđšž]')  # south slavic (slovene, croatian, bosnian, serbian)
HU_REGEX: str = build_regex('[a-záéíóöőúüű]', '[-]|[a-záéíóöőúüű]', '[a-záéíóöőúüű]')
RO_REGEX: str = build_regex('[a-zăâîșț]', '[-]|[a-zăâîșț]', '[a-zăâîșț]')
TR_REGEX: str = build_regex('[a-zçğıöşü]', '[-]|[a-zçğıöşü]', '[a-zçğıöşü]')

DEFAULT_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = {
    GameMode.NORMAL: defaultdict(lambda: 1.0),
    GameMode.HARD: defaultdict(lambda: 1.0)
}

LANGUAGES_DIRECTORY = Path('languages')


class LanguageInfo(BaseModel):
    code: str = Field(max_length=2, min_length=2) # set 1 ISO-639-1
    code_long: str = Field(max_length=3, min_length=3) # set 2/T ISO-639-2
    allowed_word_regex: str
    first_token_scores: dict[GameMode, defaultdict[str, float]] = Field(default=DEFAULT_FIRST_TOKEN_SCORES)
    score_threshold: dict[GameMode, float] = Field(default={GameMode.NORMAL: 0.05, GameMode.HARD: 0.05})


def load_token_scores_from_json(language_code: PathLike[str] | str) -> dict[GameMode, defaultdict[str, float]]:
    def load_file_or_default(code: str, mode: GameMode) -> defaultdict[str, float]:
        file_path = f'frequency_{code}_{mode.value}.json'
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    first_chars = content['first_chars']
                    assert type(first_chars) == dict
                    return defaultdict(lambda: 0.0, first_chars)
            else:
                logger.warning(f'token score file {file_path} not found, using default scores as fallback')
                return DEFAULT_FIRST_TOKEN_SCORES[mode]
        except (KeyError, AttributeError, ValueError, AssertionError, JSONDecodeError):
            logger.warning(f'there was an error loading data from {file_path}, using default scores as fallback')
            return DEFAULT_FIRST_TOKEN_SCORES[mode]

    return {
        game_mode: load_file_or_default(language_code, game_mode) for game_mode in [GameMode.NORMAL, GameMode.HARD]
    }


EN_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'en')
FR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'fr')
DE_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'de')
NL_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'nl')
ES_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'es')
PT_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'pt')
IT_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'it')
DA_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'da')
NO_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'no')
SV_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'sv')
IS_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'is')
PL_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'pl')
CS_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'cs')
SK_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'sk')
SL_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'sl')
HR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'hr')
BS_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'bs')
SR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'sr')
HU_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'hu')
RO_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'ro')
TR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json(LANGUAGES_DIRECTORY / 'tr')


class Language(Enum):
    """
    An enumeration of the languages supported by the bot.
    """
    # Latin script
    ENGLISH = LanguageInfo(code="en", code_long="eng", allowed_word_regex=EN_REGEX, first_token_scores=EN_FIRST_TOKEN_SCORES)
    FRENCH = LanguageInfo(code='fr', code_long="fra", allowed_word_regex=FR_REGEX, first_token_scores=FR_FIRST_TOKEN_SCORES)
    GERMAN = LanguageInfo(code='de', code_long="deu", allowed_word_regex=DE_REGEX, first_token_scores=DE_FIRST_TOKEN_SCORES)
    DUTCH = LanguageInfo(code='nl', code_long="nld", allowed_word_regex=NL_REGEX, first_token_scores=NL_FIRST_TOKEN_SCORES)
    SPANISH = LanguageInfo(code='es', code_long="spa", allowed_word_regex=ES_REGEX, first_token_scores=ES_FIRST_TOKEN_SCORES)
    PORTUGUESE = LanguageInfo(code='pt', code_long="por", allowed_word_regex=PT_REGEX, first_token_scores=PT_FIRST_TOKEN_SCORES)
    ITALIAN = LanguageInfo(code='it', code_long="ita", allowed_word_regex=IT_REGEX, first_token_scores=IT_FIRST_TOKEN_SCORES)
    DANISH = LanguageInfo(code='da', code_long="dan", allowed_word_regex=NN_REGEX, first_token_scores=DA_FIRST_TOKEN_SCORES)
    NORWEGIAN = LanguageInfo(code='no', code_long="nor", allowed_word_regex=NN_REGEX, first_token_scores=NO_FIRST_TOKEN_SCORES)
    SWEDISH = LanguageInfo(code='sv', code_long="swe", allowed_word_regex=SV_REGEX, first_token_scores=SV_FIRST_TOKEN_SCORES)
    ICELANDIC = LanguageInfo(code='is', code_long="isl", allowed_word_regex=IS_REGEX, first_token_scores=IS_FIRST_TOKEN_SCORES)
    POLISH = LanguageInfo(code='pl', code_long="pol", allowed_word_regex=PL_REGEX, first_token_scores=PL_FIRST_TOKEN_SCORES)
    CZECH = LanguageInfo(code='cs', code_long="ces", allowed_word_regex=CS_REGEX, first_token_scores=CS_FIRST_TOKEN_SCORES)
    SLOVAK = LanguageInfo(code='sk', code_long="slk", allowed_word_regex=CS_REGEX, first_token_scores=SK_FIRST_TOKEN_SCORES)
    SLOVENE = LanguageInfo(code='sl', code_long="slv", allowed_word_regex=SS_REGEX, first_token_scores=SL_FIRST_TOKEN_SCORES)
    CROATIAN = LanguageInfo(code='hr', code_long="hrv", allowed_word_regex=SS_REGEX, first_token_scores=HR_FIRST_TOKEN_SCORES)
    BOSNIAN = LanguageInfo(code='bs', code_long="bos", allowed_word_regex=SS_REGEX, first_token_scores=BS_FIRST_TOKEN_SCORES)
    SERBIAN = LanguageInfo(code='sr', code_long="srp", allowed_word_regex=SS_REGEX, first_token_scores=SR_FIRST_TOKEN_SCORES)
    HUNGARIAN = LanguageInfo(code='hu', code_long="hun", allowed_word_regex=HU_REGEX, first_token_scores=HU_FIRST_TOKEN_SCORES)
    ROMANIAN = LanguageInfo(code='ro', code_long="ron", allowed_word_regex=RO_REGEX, first_token_scores=RO_FIRST_TOKEN_SCORES)
    TURKISH = LanguageInfo(code='tr', code_long="tur", allowed_word_regex=TR_REGEX, first_token_scores=TR_FIRST_TOKEN_SCORES)

    @classmethod
    def from_language_code(cls, code: str):
        matches = [e for e in cls if e.value.code == code]
        if matches:
            return matches[0]
        else:
            raise ValueError(f'no language found for code "{code}"')
