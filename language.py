import json
import logging
import os.path
from collections import defaultdict
from enum import Enum
from json import JSONDecodeError

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
SQ_REGEX: str = build_regex('[a-zëç]', '[-]|[a-zëç]', '[a-zëç]')  # albanian
GA_REGEX: str = build_regex('[a-záéíóú]', '[-]|[a-záéíóú]', '[a-záéíóú]')  # irish
GD_REGEX: str = build_regex('[a-zàèìòù]', '[-]|[a-zàèìòù]', '[a-zàèìòù]')  # scottish, gaelic
CY_REGEX: str = build_regex('[a-zâêîôûŷ]', '[-]|[a-zâêîôûŷ]', '[a-zâêîôûŷ]')  # welsh
MT_REGEX: str = build_regex('[a-zċġħż]', '[-]|[a-zċġħż]', '[a-zċġħż]')  # maltese
TR_REGEX: str = build_regex('[a-zçğıöşü]', '[-]|[a-zçğıöşü]', '[a-zçğıöşü]')

DEFAULT_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = {
    GameMode.NORMAL: defaultdict(lambda: 1.0),
    GameMode.HARD: defaultdict(lambda: 1.0)
}


class LanguageInfo(BaseModel):
    code: str = Field(max_length=2, min_length=2)
    allowed_word_regex: str
    first_token_scores: dict[GameMode, defaultdict[str, float]] = Field(default=DEFAULT_FIRST_TOKEN_SCORES)
    score_threshold: dict[GameMode, float] = Field(default={GameMode.NORMAL: 0.05, GameMode.HARD: 0.05})


def load_token_scores_from_json(language_code: str) -> dict[GameMode, defaultdict[str, float]]:
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


EN_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('en')
DE_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('de')
FR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('fr')
ES_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('es')
IT_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('it')
TR_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('tr')
SV_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('sv')
DA_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('da')
NO_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('no')
NL_FIRST_TOKEN_SCORES: dict[GameMode, defaultdict[str, float]] = load_token_scores_from_json('nl')

class Language(Enum):
    """
    An enumeration of the languages supported by the bot.
    """
    # Latin script
    ENGLISH = LanguageInfo(code="en", allowed_word_regex=EN_REGEX, first_token_scores=EN_FIRST_TOKEN_SCORES)
    FRENCH = LanguageInfo(code='fr', allowed_word_regex=FR_REGEX, first_token_scores=FR_FIRST_TOKEN_SCORES)
    GERMAN = LanguageInfo(code='de', allowed_word_regex=DE_REGEX, first_token_scores=DE_FIRST_TOKEN_SCORES)
    DUTCH = LanguageInfo(code='nl', allowed_word_regex=NL_REGEX, first_token_scores=NL_FIRST_TOKEN_SCORES)
    LUXEMBOURGISH = LanguageInfo(code='lb', allowed_word_regex=DE_REGEX)
    SPANISH = LanguageInfo(code='es', allowed_word_regex=ES_REGEX, first_token_scores=ES_FIRST_TOKEN_SCORES)
    PORTUGUESE = LanguageInfo(code='pt', allowed_word_regex=PT_REGEX)
    ITALIAN = LanguageInfo(code='it', allowed_word_regex=IT_REGEX, first_token_scores=IT_FIRST_TOKEN_SCORES)
    CATALAN = LanguageInfo(code='ca', allowed_word_regex=FR_REGEX)
    GALICIAN = LanguageInfo(code='gl', allowed_word_regex=FR_REGEX)
    DANISH = LanguageInfo(code='da', allowed_word_regex=NN_REGEX, first_token_scores=DA_FIRST_TOKEN_SCORES)
    NORWEGIAN = LanguageInfo(code='no', allowed_word_regex=NN_REGEX, first_token_scores=NO_FIRST_TOKEN_SCORES)
    SWEDISH = LanguageInfo(code='sv', allowed_word_regex=SV_REGEX, first_token_scores=SV_FIRST_TOKEN_SCORES)
    ICELANDIC = LanguageInfo(code='is', allowed_word_regex=IS_REGEX)
    FAROESE = LanguageInfo(code='fo', allowed_word_regex=IS_REGEX)
    POLISH = LanguageInfo(code='pl', allowed_word_regex=PL_REGEX)
    CZECH = LanguageInfo(code='cs', allowed_word_regex=CS_REGEX)
    SLOVAK = LanguageInfo(code='sk', allowed_word_regex=CS_REGEX)
    SLOVENE = LanguageInfo(code='sl', allowed_word_regex=SS_REGEX)
    CROATIAN = LanguageInfo(code='hr', allowed_word_regex=SS_REGEX)
    BOSNIAN = LanguageInfo(code='bs', allowed_word_regex=SS_REGEX)
    SERBIAN = LanguageInfo(code='sr', allowed_word_regex=SS_REGEX)
    HUNGARIAN = LanguageInfo(code='hu', allowed_word_regex=HU_REGEX)
    ROMANIAN = LanguageInfo(code='ro', allowed_word_regex=RO_REGEX)
    ALBANIAN = LanguageInfo(code='sq', allowed_word_regex=SQ_REGEX)
    IRISH = LanguageInfo(code='ga', allowed_word_regex=GA_REGEX)
    SCOTTISH_GAELIC = LanguageInfo(code='gd', allowed_word_regex=GD_REGEX)
    WELSH = LanguageInfo(code='cy', allowed_word_regex=CY_REGEX)
    BRETON = LanguageInfo(code='br', allowed_word_regex=FR_REGEX)
    BASQUE = LanguageInfo(code='eu', allowed_word_regex=ES_REGEX)
    MALTESE = LanguageInfo(code='mt', allowed_word_regex=MT_REGEX)
    TURKISH = LanguageInfo(code='tr', allowed_word_regex=TR_REGEX)

    @classmethod
    def from_language_code(cls, code: str):
        matches = [e for e in cls if e.value.code == code]
        if matches:
            return matches[0]
        else:
            raise ValueError(f'no language found for code "{code}"')
