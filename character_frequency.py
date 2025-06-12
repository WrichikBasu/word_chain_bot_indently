import json
import string
from collections import defaultdict

from pydantic import BaseModel


class Result(BaseModel):
    first_chars: dict[str, float]
    last_chars: dict[str, float]
    only_start_chars: list[str]
    only_end_chars: list[str]


def word_list() -> list[str]:
    # words_alpha.txt must be a line break delimited file containing the words
    # we use this dictionary: https://raw.githubusercontent.com/dwyl/english-words/refs/heads/master/words_alpha.txt
    with open('words_alpha.txt', 'r') as dictionary_file:
        words = [line.strip() for line in dictionary_file]
        return words


def analyze(token_width=1) -> Result:
    """
    Analyzes the dictionary and returns a frequency list per letter.
    :param token_width: width of token in the start and end of the word
    :return: result object
    """
    valid_words = [word for word in word_list() if len(word) >= token_width]
    first_char_occurrences = defaultdict(lambda: 0)
    last_char_occurrences = defaultdict(lambda: 0)

    for word in valid_words:
        start_token = word[:token_width]
        first_char_occurrences[start_token] += 1
        end_token = word[-token_width:]
        last_char_occurrences[end_token] += 1

    tokens = [(l1 + l2) for l1 in string.ascii_lowercase for l2 in string.ascii_lowercase]
    total_words = len(valid_words)
    total_tokens = len(tokens)
    return Result(
        first_chars={token: first_char_occurrences[token] / total_words * total_tokens for token in tokens},
        last_chars={token: last_char_occurrences[token] / total_words * total_tokens for token in tokens},
        only_start_chars=sorted([token for token in first_char_occurrences if last_char_occurrences[token] == 0]),
        only_end_chars=sorted([token for token in last_char_occurrences if first_char_occurrences[token] == 0])
    )

if __name__ == '__main__':
    result = analyze(2)
    with open('frequency.json', 'w') as export_file:
        json.dump(result.model_dump(), export_file, indent=4, sort_keys=True)
