import json
import os
import re
from multiprocessing.pool import Pool

from pydantic import BaseModel

from language import Language, LanguageInfo

THREAD_COUNT = os.cpu_count()

class Result(BaseModel):
    matches: list[str]
    non_matches: list[str]
    code: str

def load_file(file_name: str) -> list[str]:
    with open(file_name, 'r', encoding='utf-8') as dictionary_file:
        words = [line.strip() for line in dictionary_file]
        return words

def compute_batch(words: list[str], regex: re.Pattern[str]) -> tuple[set[str], set[str]]:
    matches = set()
    non_matches = set()
    for word in words:
        word_lower = word.lower()
        if regex.match(word_lower):
            matches.add(word_lower)
        else:
            non_matches.add(word_lower)
    return matches, non_matches

def analyze(language: LanguageInfo, words: list[str]) -> Result:
    valid_words = [word.lower() for word in words if len(word) > 1 and ' ' not in word]
    total_matches = set()
    total_non_matches = set()
    num_words = len(valid_words)

    chunk_size = (num_words + THREAD_COUNT - 1) // THREAD_COUNT
    chunks = [valid_words[i * chunk_size:(i + 1) * chunk_size] for i in range((num_words + THREAD_COUNT - 1) // chunk_size)]

    regex = re.compile(language.allowed_word_regex)

    with Pool(THREAD_COUNT) as pool:
        pool_results = pool.starmap(compute_batch, [(chunk, regex) for chunk in chunks])

    for matches, non_matches in pool_results:
        total_matches.update(matches)
        total_non_matches.update(non_matches)

    return Result(
        matches=list(total_matches),
        non_matches=list(total_non_matches),
        code=language.code
    )

def main(language: Language):
    words = load_file(f'words_{language.value.code}.txt')
    num_words = len(words)
    result = analyze(language.value, words)
    print(f'{(len(result.matches)/num_words):.2%} words matches')
    print(f'{(len(result.non_matches)/num_words):.2%} words did not match')
    print(f'{((num_words - (len(result.matches) + len(result.non_matches))) / num_words):.2%} words refused')
    with open(f'dictionary_check_{language.value.code}.json', 'w') as export_file:
        json.dump(result.model_dump(), export_file, indent=4, sort_keys=True, ensure_ascii=False)

if __name__ == '__main__':
    main(Language.ENGLISH)