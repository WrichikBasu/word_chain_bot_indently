from enum import Enum

from pydantic import BaseModel, Field


def build_regex(start_group: str, middle_group: str, end_group: str) -> str:
    return rf'^({start_group})({middle_group})*({end_group})$'

EN_REGEX: str = build_regex('[a-z]', '[-]|[a-z]', '[a-z]')
FR_REGEX: str = build_regex('[a-zàâæçéèêëîïôœùûüÿ]', '[-]|[a-zàâæçéèêëîïôœùûüÿ]', '[a-zàâæçéèêëîïôœùûüÿ]')
DE_REGEX: str = build_regex('[a-zäöü]', '[-]|[a-zäöüß]', '[a-zäöüß]')
NL_REGEX: str = build_regex('[a-zéèëç]', '[-]|[a-zéèëç]', '[a-zéèëç]')
ES_REGEX: str = build_regex('[a-záéíóúüñ]','[-]|[a-záéíóúüñ]','[a-záéíóúüñ]')
PT_REGEX: str = build_regex('[a-záâãàçéêíóôõú]', '[-]|[a-záâãàçéêíóôõú]', '[a-záâãàçéêíóôõú]')
IT_REGEX: str = build_regex('[a-zàèéìíîòóùú]', '[-]|[a-zàèéìíîòóùú]', '[a-zàèéìíîòóùú]')
NN_REGEX: str = build_regex('[a-zæøå]', '[-]|[a-zæøå]', '[a-zæøå]') # north germanic (danish, norwegian)
SV_REGEX: str = build_regex('[a-zåäö]', '[a-zåäö]', '[a-zåäö]')
IS_REGEX: str = build_regex('[a-záéíóúýþæö]', '[-]|[a-záéíóúýþæöð]', '[a-záéíóúýþæöð]') # icelandic and faroese
PL_REGEX: str = build_regex('[a-ząćęłńóśźż]', '[-]|[a-ząćęłńóśźż]', '[a-ząćęłńóśźż]')
CS_REGEX: str = build_regex('[a-záčďéěíňóřšťůýž]', '[-]|[a-záčďéěíňóřšťůýž]', '[a-záčďéěíňóřšťůýž]')  # czech and slovak
SS_REGEX: str = build_regex('[a-zčćđšž]', '[-]|[a-zčćđšž]', '[a-zčćđšž]')  # south slavic (slovene, croatian, bosnian, serbian)
HU_REGEX: str = build_regex('[a-záéíóöőúüű]', '[-]|[a-záéíóöőúüű]', '[a-záéíóöőúüű]')
RO_REGEX: str = build_regex('[a-zăâîșț]', '[-]|[a-zăâîșț]', '[a-zăâîșț]')
SQ_REGEX: str = build_regex('[a-zëç]', '[-]|[a-zëç]', '[a-zëç]') # albanian
GA_REGEX: str = build_regex('[a-záéíóú]', '[-]|[a-záéíóú]', '[a-záéíóú]')  # irish
GD_REGEX: str = build_regex('[a-zàèìòù]', '[-]|[a-zàèìòù]', '[a-zàèìòù]')  # scottish, gaelic
CY_REGEX: str = build_regex('[a-zâêîôûŷ]', '[-]|[a-zâêîôûŷ]', '[a-zâêîôûŷ]')  # welsh
MT_REGEX: str = build_regex('[a-zċġħż]', '[-]|[a-zċġħż]', '[a-zċġħż]')  # maltese
TR_REGEX: str = build_regex('[a-zçğıöşü]', '[-]|[a-zçğıöşü]', '[a-zçğıöşü]')


class LanguageInfo(BaseModel):
    code: str = Field(max_length=2, min_length=2)
    allowed_word_regex: str

class Language(Enum):
    """
    An enumeration of the languages supported by the bot.
    """
    # Latin script
    ENGLISH = LanguageInfo(code="en", allowed_word_regex=EN_REGEX)
    FRENCH = LanguageInfo(code='fr', allowed_word_regex=FR_REGEX)
    GERMAN = LanguageInfo(code='de', allowed_word_regex=DE_REGEX)
    DUTCH = LanguageInfo(code='nl', allowed_word_regex=NL_REGEX)
    LUXEMBOURGISH = LanguageInfo(code='lb', allowed_word_regex=DE_REGEX)
    SPANISH = LanguageInfo(code='es', allowed_word_regex=ES_REGEX)
    PORTUGUESE = LanguageInfo(code='pt', allowed_word_regex=PT_REGEX)
    ITALIAN = LanguageInfo(code='it', allowed_word_regex=IT_REGEX)
    CATALAN = LanguageInfo(code='ca', allowed_word_regex=FR_REGEX)
    GALICIAN = LanguageInfo(code='gl', allowed_word_regex=FR_REGEX)
    DANISH = LanguageInfo(code='da', allowed_word_regex=NN_REGEX)
    NORWEGIAN = LanguageInfo(code='no', allowed_word_regex=NN_REGEX)
    SWEDISH = LanguageInfo(code='sv', allowed_word_regex=SV_REGEX)
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
