import asyncio
import json
import logging
import os
import re
import string
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Callable

from consts import GameMode
from language import LANGUAGES_DIRECTORY, Language
from wortschatz import CorporaSize, extract_words


class ComputedDefaultDict(defaultdict):

    def __init__(self, default_factory: Callable, initial_values: dict | None):
        super().__init__(default_factory, initial_values)

    def __missing__(self, key):
        self[key] = value = self.default_factory(key)
        return value


__LOGGER = logging.getLogger(__name__)
__CACHE_DIRECTORY = LANGUAGES_DIRECTORY / Path('cache')
__DEFAULT_SIZE = CorporaSize.Size_30K.value
__LANGUAGE_SOURCES: dict[Language, str] = ComputedDefaultDict(lambda k: f'https://downloads.wortschatz-leipzig.de/corpora/{k.value.code_long}_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz', {
    Language.ENGLISH: f'https://downloads.wortschatz-leipzig.de/corpora/eng-simple_wikipedia_2021_{__DEFAULT_SIZE}.tar.gz'
})


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

    for l in Language:
        asyncio.run(main(l))
