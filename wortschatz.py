import logging
import os
import tarfile
import tempfile
from enum import Enum
from os import PathLike
from urllib.parse import urlparse

import aiofiles
import aiohttp

"""
Module to query data from Wortschatz project of university of Leipzig
"""

__LOGGER = logging.getLogger(__name__)


class CorporaSize(str, Enum):
    Size_10K = '10K',
    Size_30K = '30K',
    Size_100K = '100K',
    Size_300K = '300K',
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


async def __load_words(extracted_directory: PathLike[str] | str) -> list[str]:
    # Find the *-words.txt file inside the extracted directory
    words_file = None
    for file in os.listdir(extracted_directory):
        if file.endswith("-words.txt"):
            words_file = os.path.join(extracted_directory, file)
            break

    if not words_file:
        raise FileNotFoundError("No *-words.txt file found in the extracted directory.")

    # Process the file
    result = set()
    async with aiofiles.open(words_file, "r", encoding="utf-8") as f:
        contents = await f.read()
        __LOGGER.info('word file read')
        # each line is tab-separated into word-id, word, occurrences
        # word-ids until 100 are usually special characters
        for line in contents.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                result.add(parts[1].lower())

    return list(result)


async def extract_words(url: str, cache_directory: PathLike[str] | str | None = None) -> list[str]:
    if not cache_directory:
        with tempfile.TemporaryDirectory() as temp_directory:
            extracted_directory = await __download_and_extract_tar(url, temp_directory)
            return await __load_words(extracted_directory)
    else:
        extracted_directory = await __download_and_extract_tar(url, cache_directory)
        return await __load_words(extracted_directory)
