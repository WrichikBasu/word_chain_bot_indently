import json
import os
import re
import string
from collections import defaultdict
from itertools import product

import requests
from pydantic import BaseModel

from language import Language

__LANGUAGE_SOURCES: dict[Language, str] = {
    Language.ENGLISH: 'https://raw.githubusercontent.com/dwyl/english-words/refs/heads/master/words_alpha.txt',
    Language.GERMAN: 'https://gist.github.com/MarvinJWendt/2f4f4154b8ae218600eb091a5706b5f4/raw/36b70dd6be330aa61cd4d4cdfda6234dcb0b8784/wordlist-german.txt',
    Language.FRENCH: 'https://github.com/hbenbel/French-Dictionary/raw/refs/heads/master/dictionary/dictionary.csv',
    Language.SPANISH: 'https://github.com/xavier-hernandez/spanish-wordlist/raw/refs/heads/main/text/spanish_words.txt',
    Language.ITALIAN: 'https://github.com/napolux/paroleitaliane/raw/refs/heads/main/paroleitaliane/60000_parole_italiane.txt',
    Language.TURKISH: 'https://github.com/mertemin/turkish-word-list/raw/refs/heads/master/words.txt'
}


class Result(BaseModel):
    first_chars: dict[str, float]
    last_chars: dict[str, float]
    only_start_chars: list[str]
    only_end_chars: list[str]


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

def main(language: Language, token_width: int = 1):
    dictionary_file_name = f'words_{language.value.code}.txt'
    if not os.path.exists(dictionary_file_name):
        with requests.get(__LANGUAGE_SOURCES[language], stream=True) as r:
            r.raise_for_status()
            with open(dictionary_file_name, 'w', encoding='utf-8') as f:
                for line in r.iter_lines():  # type: bytes
                    try:
                        f.write(f'{line.decode('utf-8')}\n')
                    except UnicodeError:
                        pass

    words = load_file(dictionary_file_name)
    regex = re.compile(language.value.allowed_word_regex)
    accepted_words = [word for word in words if regex.match(word)]
    result = analyze(accepted_words, token_width)
    with open(f'frequency_{language.value.code}_{token_width}.json', 'w', encoding='utf-8') as export_file:
        json.dump(result.model_dump(), export_file, indent=4, sort_keys=True, ensure_ascii=False)

if __name__ == '__main__':
    for l in __LANGUAGE_SOURCES.keys():
        for t in [1, 2]:
            main(l, t)
