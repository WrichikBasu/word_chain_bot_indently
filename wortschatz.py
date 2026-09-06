import logging
import os
import tarfile
import tempfile
from collections import defaultdict
from enum import Enum
from os import PathLike
from typing import NamedTuple
from urllib.parse import urlparse

import aiofiles
import aiohttp

"""
Module to query data from Wortschatz project of university of Leipzig
"""

__LOGGER = logging.getLogger(__name__)
__READ_BATCH_SIZE = 1024 * 1024  # bytes of lines to hand over per read, for files too large to read at once


class Word(NamedTuple):
    """A single entry of the corpus word list, in its original capitalization."""
    content: str
    occurrences: int


class CorporaSize(str, Enum):
    Size_10K = '10K'
    Size_30K = '30K'
    Size_100K = '100K'
    Size_300K = '300K'
    Size_1M = '1M'


async def __download_and_extract_tar(url: str, extraction_directory: PathLike[str] | str) -> PathLike[str] | str:
    # Extract the original filename from the URL and remove the extension
    parsed_url = urlparse(url)
    original_filename = os.path.basename(parsed_url.path)
    extension = '.tar.gz'
    if original_filename.endswith(extension):
        original_filename = original_filename[:-len(extension)]  # Remove .tar.gz
    else:
        raise ValueError(f"file is not a {extension}")

    extracted_directory = os.path.join(extraction_directory, original_filename)
    if not os.path.exists(extracted_directory):
        __LOGGER.info(f'{original_filename} does not exist, proceed with download')
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download file: HTTP {response.status}")

                tar_path = os.path.join(extraction_directory, f"{original_filename}{extension}")
                # Save the downloaded file
                async with aiofiles.open(tar_path, "wb") as f:
                    await f.write(await response.read())
                    __LOGGER.info('file downloaded and saved to disk')

                # Extract the tar.gz file
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=extraction_directory, filter='tar')
                    __LOGGER.info('file extracted')
    else:
        __LOGGER.info(f'{original_filename} already exists, using from cache')

    return extracted_directory


async def __load_words(extracted_directory: PathLike[str] | str) -> dict[int, Word]:
    # Find the *-words.txt file inside the extracted directory
    file_ending = "-words.txt"
    words_file = next((os.path.join(extracted_directory, file) for file in os.listdir(extracted_directory)
                       if file.endswith(file_ending)), None)

    if not words_file:
        raise FileNotFoundError(f"No {file_ending} file found in the extracted directory.")

    # Process the file
    result = {}
    async with aiofiles.open(words_file, "r", encoding="utf-8") as f:
        contents = await f.read()
        __LOGGER.info('word file read')
        # each line is tab-separated into word-id, word, occurrences
        # word-ids until 100 are usually special characters
        for line in contents.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                result[int(parts[0])] = Word(content=parts[1], occurrences=int(parts[2]))

    return result


async def __load_word_positions(extracted_directory: PathLike[str] | str) -> dict[int, list[int]]:
    # Find the *-inv_w.txt file inside the extracted directory
    file_ending = "-inv_w.txt"
    word_positions_file = next((os.path.join(extracted_directory, file) for file in os.listdir(extracted_directory)
                                if file.endswith(file_ending)), None)

    if not word_positions_file:
        raise FileNotFoundError(f"No *{file_ending} file found in the extracted directory.")

    result = defaultdict[int, list[int]](list)
    async with aiofiles.open(word_positions_file, "r", encoding="utf-8") as f:
        # read in batches, because iterating the file line by line costs one thread round-trip per line
        while lines := await f.readlines(__READ_BATCH_SIZE):
            # each line is tab-separated into word-id, sentence-id, word-position
            for line in lines:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    word_id = int(parts[0])
                    word_position = int(parts[2])
                    result[word_id].append(word_position)
    __LOGGER.info('word position file read')

    # convert from defaultdict to ordinary dict
    return {word_id: positions for word_id, positions in result.items()}


async def extract_words(url: str, cache_directory: PathLike[str] | str | None = None) -> dict[int, Word]:
    if not cache_directory:
        with tempfile.TemporaryDirectory() as temp_directory:
            extracted_directory = await __download_and_extract_tar(url, temp_directory)
            return await __load_words(extracted_directory)
    else:
        extracted_directory = await __download_and_extract_tar(url, cache_directory)
        return await __load_words(extracted_directory)


async def extract_word_positions(url: str, cache_directory: PathLike[str] | str | None = None) -> dict[int, list[int]]:
    if not cache_directory:
        with tempfile.TemporaryDirectory() as temp_directory:
            extracted_directory = await __download_and_extract_tar(url, temp_directory)
            return await __load_word_positions(extracted_directory)
    else:
        extracted_directory = await __download_and_extract_tar(url, cache_directory)
        return await __load_word_positions(extracted_directory)
