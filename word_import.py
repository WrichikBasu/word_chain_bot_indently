import argparse
import asyncio

from sqlalchemy.sql.expression import insert

from character_frequency import (__CACHE_DIRECTORY, __LANGUAGE_SOURCES, accepted_words,
                                 words_with_more_than_n_occurrences)
from language import Language
from main import word_chain_bot
from model import WordCacheModel
from wortschatz import extract_words


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--language', type=str, help='ISO-639-1 language code', required=True)

    args = parser.parse_args()
    language = Language.from_language_code(args.language)

    extracted_words_dict = await extract_words(__LANGUAGE_SOURCES[language], __CACHE_DIRECTORY)
    language_gated_words = accepted_words(extracted_words_dict, language)
    occurrence_gated_words = words_with_more_than_n_occurrences(language_gated_words, 1, False)
    total_words = len(occurrence_gated_words)

    async with word_chain_bot.db_connection(locked=True) as connection:
        for index, word in enumerate(occurrence_gated_words):
            statement = insert(WordCacheModel).values(
                word=word,
                language=language.value.code
            ).prefix_with('OR IGNORE')
            await connection.execute(statement)
            if index % 100 == 0:
                print(f'({(index/total_words):.2%}) {index}/{total_words}')
        await connection.commit()
    print(f'finished importing {total_words} words')

if __name__ == '__main__':
    asyncio.run(main())
