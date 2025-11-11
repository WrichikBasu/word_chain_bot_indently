import asyncio
import json
import logging
import os
import re
import string
from collections import defaultdict
from itertools import product
from pathlib import Path

from consts import GameMode
from language import LANGUAGES_DIRECTORY, Language
from wortschatz import CorporaSize, extract_words

__LOGGER = logging.getLogger(__name__)
__CACHE_DIRECTORY = LANGUAGES_DIRECTORY / Path('cache')
__DEFAULT_SIZE = CorporaSize.Size_30K.value
__LANGUAGE_SOURCES: dict[Language, str] = {
    Language.ENGLISH: f'https://downloads.wortschatz-leipzig.de/corpora/eng-simple_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.FRENCH: f'https://downloads.wortschatz-leipzig.de/corpora/fra_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.GERMAN: f'https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.DUTCH: f'https://downloads.wortschatz-leipzig.de/corpora/nld_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SPANISH: f'https://downloads.wortschatz-leipzig.de/corpora/spa_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.PORTUGUESE: f'https://downloads.wortschatz-leipzig.de/corpora/por_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ITALIAN: f'https://downloads.wortschatz-leipzig.de/corpora/ita_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.DANISH: f'https://downloads.wortschatz-leipzig.de/corpora/dan_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.NORWEGIAN: f'https://downloads.wortschatz-leipzig.de/corpora/nor_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SWEDISH: f'https://downloads.wortschatz-leipzig.de/corpora/swe_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ICELANDIC: f'https://downloads.wortschatz-leipzig.de/corpora/isl_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.POLISH: f'https://downloads.wortschatz-leipzig.de/corpora/pol_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.CZECH: f'https://downloads.wortschatz-leipzig.de/corpora/ces_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SLOVAK: f'https://downloads.wortschatz-leipzig.de/corpora/slk_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SLOVENE: f'https://downloads.wortschatz-leipzig.de/corpora/slv_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.CROATIAN: f'https://downloads.wortschatz-leipzig.de/corpora/hrv_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.BOSNIAN: f'https://downloads.wortschatz-leipzig.de/corpora/bos_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.SERBIAN: f'https://downloads.wortschatz-leipzig.de/corpora/srp_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.HUNGARIAN: f'https://downloads.wortschatz-leipzig.de/corpora/hun_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.ROMANIAN: f'https://downloads.wortschatz-leipzig.de/corpora/ron_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz',
    Language.TURKISH: f'https://downloads.wortschatz-leipzig.de/corpora/tur_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz'
}


def generate_token_scores(words: list[str], game_modes: list[GameMode]) -> dict[int, dict[str, float]]:
    scores: dict[int, dict[str, float]] = dict()

    for game_mode in game_modes:
        token_width = int(game_mode.value)
        token_occurrences = defaultdict(lambda: 0)
        single_tokens = set(string.ascii_lowercase)
        valid_words = [word.lower() for word in words if len(word) >= token_width]

        for word in valid_words:
            start_token = word[:token_width]
            token_occurrences[start_token] += 1
            single_tokens.update(set([c for c in word]))

        tokens = [''.join(c) for c in product(*[single_tokens for _ in range(token_width)])]
        total_words = len(valid_words)
        total_tokens = len(tokens)

        scores[token_width] = {token: token_occurrences[token] / total_words * total_tokens for token in tokens}

    return scores

async def main(language: Language):
    __LOGGER.info(f'analyzing for {language.value.code}')
    words = await extract_words(__LANGUAGE_SOURCES[language], __CACHE_DIRECTORY)
    regex = re.compile(language.value.allowed_word_regex)
    accepted_words = [word for word in words if regex.match(word)]
    result = generate_token_scores(accepted_words, [game_mode for game_mode in GameMode])
    with open(LANGUAGES_DIRECTORY / f'scores_{language.value.code}.json', 'w', encoding='utf-8') as export_file:
        json.dump(result, export_file, indent=4, sort_keys=True, ensure_ascii=False)
        __LOGGER.info(f'analyzed and exported for {language.value.code}')

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    if not os.path.exists(LANGUAGES_DIRECTORY):
        os.mkdir(LANGUAGES_DIRECTORY)
    if not os.path.exists(__CACHE_DIRECTORY):
        os.mkdir(__CACHE_DIRECTORY)

    for l in __LANGUAGE_SOURCES.keys():
        asyncio.run(main(l))
