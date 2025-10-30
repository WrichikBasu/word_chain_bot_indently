import os
import tarfile
import tempfile
from urllib.parse import urlparse

import aiohttp
import aiofiles
from enum import Enum
import logging

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

async def extract_words(url: str, cache_directory: os.PathLike[str] | str | None = None) -> list[str]:
    # Extract the original filename from the URL and remove the extension
    parsed_url = urlparse(url)
    original_filename = os.path.basename(parsed_url.path)
    if original_filename.endswith('.tar.gz'):
        original_filename = original_filename[:-7]  # Remove .tar.gz
    else:
        raise ValueError("file is not a .tar.gz")

    extracted_dir = os.path.join(cache_directory, original_filename)
    if not cache_directory or not os.path.exists(extracted_dir):
        __LOGGER.info(f'{original_filename} does not exist, proceed with download')
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to download file: HTTP {response.status}")

                if cache_directory:
                    tar_path = os.path.join(cache_directory, f"{original_filename}.tar.gz")

                    # Save the downloaded file
                    async with aiofiles.open(tar_path, "wb") as f:
                        await f.write(await response.read())
                        __LOGGER.info('file downloaded and saved to disc')

                    # Extract the tar.gz file
                    with tarfile.open(tar_path, "r:gz") as tar:
                        tar.extractall(path=cache_directory, filter='tar')
                        __LOGGER.info('file extracted')

                else:
                    # Create a temporary directory (automatically cleaned up)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tar_path = os.path.join(tmpdir, "corpus.tar.gz")

                        # Save the downloaded file
                        async with aiofiles.open(tar_path, "wb") as f:
                            await f.write(await response.read())
                            __LOGGER.info('file downloaded and saved to disc')

                        # Extract the tar.gz file
                        with tarfile.open(tar_path, "r:gz") as tar:
                            tar.extractall(path=tmpdir, filter='tar')
                            __LOGGER.info('file extracted')

    if not os.path.isdir(extracted_dir):
        raise FileNotFoundError(f"Extracted directory not found: {original_filename}")

    # Find the *-words.txt file inside the extracted directory
    words_file = None
    for file in os.listdir(extracted_dir):
        if file.endswith("-words.txt"):
            words_file = os.path.join(extracted_dir, file)
            break

    if not words_file:
        raise FileNotFoundError("No *-words.txt file found in the extracted directory.")

    # Process the file
    result = []
    async with aiofiles.open(words_file, "r", encoding="utf-8") as f:
        contents = await f.read()
        __LOGGER.info('word file read')
        # each line is tab-separated into word-id, word, occurrences
        # word-ids until 100 are usually special characters
        for line in contents.splitlines():
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                result.append(parts[1])

    return result
