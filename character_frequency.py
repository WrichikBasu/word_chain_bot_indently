import asyncio
import json
import logging
import os
import re
import string
from collections import defaultdict
from itertools import product
from pathlib import Path

import requests
from pydantic import BaseModel

from language import LANGUAGES_DIRECTORY, Language
from wortschatz import CorporaSize, extract_words

__LOGGER = logging.getLogger(__name__)
__CACHE_DIRECTORY = LANGUAGES_DIRECTORY / Path('cache')
__DEFAULT_SIZE = CorporaSize.Size_30K.value
__LANGUAGE_SOURCES: dict[Language, str] = {
    Language.ENGLISH: f'https://downloads.wortschatz-leipzig.de/corpora/eng-simple_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.GERMAN: f'https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.FRENCH: f'https://downloads.wortschatz-leipzig.de/corpora/fra_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SPANISH: f'https://downloads.wortschatz-leipzig.de/corpora/spa_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ITALIAN: f'https://downloads.wortschatz-leipzig.de/corpora/ita_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.PORTUGUESE: f'https://downloads.wortschatz-leipzig.de/corpora/por_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.TURKISH: f'https://downloads.wortschatz-leipzig.de/corpora/tur_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SWEDISH: f'https://downloads.wortschatz-leipzig.de/corpora/swe_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.DANISH: f'https://downloads.wortschatz-leipzig.de/corpora/dan_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.NORWEGIAN: f'https://downloads.wortschatz-leipzig.de/corpora/nor_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.DUTCH: f'https://downloads.wortschatz-leipzig.de/corpora/nld_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.CROATIAN: f'https://downloads.wortschatz-leipzig.de/corpora/hrv_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SERBIAN: f'https://downloads.wortschatz-leipzig.de/corpora/srp_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SLOVENE: f'https://downloads.wortschatz-leipzig.de/corpora/slv_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SLOVAK: f'https://downloads.wortschatz-leipzig.de/corpora/slk_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.HUNGARIAN: f'https://downloads.wortschatz-leipzig.de/corpora/hun_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ROMANIAN: f'https://downloads.wortschatz-leipzig.de/corpora/ron_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz'
}


class Result(BaseModel):
    first_chars: dict[str, float]
    last_chars: dict[str, float]
    only_start_chars: list[str]
    only_end_chars: list[str]


def download_file(file_name: str, url: str):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(file_name, 'w', encoding='utf-8') as f:
            for line in r.iter_lines():  # type: bytes
                try:
                    f.write(f'{line.decode('utf-8')}\n')
                except UnicodeError:
                    pass

def load_file(file_name: str) -> list[str]:
    with open(file_name, 'r', encoding='utf-8') as dictionary_file:
        words = [line.strip() for line in dictionary_file]
        return words


def analyze(words: list[str], token_width=1) -> Result:
    """
    Analyzes the dictionary and returns a frequency list per letter.
    :param words: list of words to check
    :param token_width: width of token in the start and end of the word
    :return: result object
    """
    valid_words = [word.lower() for word in words if len(word) >= token_width]
    first_char_occurrences = defaultdict(lambda: 0)
    last_char_occurrences = defaultdict(lambda: 0)
    single_tokens = set(string.ascii_lowercase)

    for word in valid_words:
        start_token = word[:token_width]
        first_char_occurrences[start_token] += 1
        end_token = word[-token_width:]
        last_char_occurrences[end_token] += 1
        single_tokens.update(set([c for c in word]))

    tokens = [''.join(c) for c in product(*[single_tokens for _ in range(token_width)])]
    total_words = len(valid_words)
    total_tokens = len(tokens)
    return Result(
        first_chars={token: first_char_occurrences[token] / total_words * total_tokens for token in tokens},
        last_chars={token: last_char_occurrences[token] / total_words * total_tokens for token in tokens},
        only_start_chars=sorted([token for token in first_char_occurrences if last_char_occurrences[token] == 0]),
        only_end_chars=sorted([token for token in last_char_occurrences if first_char_occurrences[token] == 0])
    )

async def main(language: Language, token_width: int = 1):
    __LOGGER.info(f'analyzing for {language.value.code}')
    words = await extract_words(__LANGUAGE_SOURCES[language], __CACHE_DIRECTORY)
    regex = re.compile(language.value.allowed_word_regex)
    accepted_words = [word for word in words if regex.match(word)]
    result = analyze(accepted_words, token_width)
    with open(LANGUAGES_DIRECTORY / f'frequency_{language.value.code}_{token_width}.json', 'w', encoding='utf-8') as export_file:
        json.dump(result.model_dump(), export_file, indent=4, sort_keys=True, ensure_ascii=False)
        __LOGGER.info(f'analyzed and exported for {language.value.code}')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if not os.path.exists(LANGUAGES_DIRECTORY):
        os.mkdir(LANGUAGES_DIRECTORY)
    if not os.path.exists(__CACHE_DIRECTORY):
        os.mkdir(__CACHE_DIRECTORY)

    for l in __LANGUAGE_SOURCES.keys():
        for t in [1, 2]:
            asyncio.run(main(l, t))
