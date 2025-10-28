import asyncio
import os
import tarfile
import tempfile
from urllib.parse import urlparse

import aiohttp
import aiofiles

from character_frequency import analyze

"""
Module to query data from Wortschatz project of university of Leipzig
"""

async def extract_words(url: str) -> list[str]:
    """
    Async function to download a .tar.gz file, extract it, find the *-words.txt file,
    and return all entries from the second column.

    Args:
        url: URL of the .tar.gz file to download.

    Returns:
        List of words from the second column.
    """
    # Extract the original filename from the URL and remove the extension
    parsed_url = urlparse(url)
    original_filename = os.path.basename(parsed_url.path)
    if original_filename.endswith('.tar.gz'):
        original_filename = original_filename[:-7]  # Remove .tar.gz

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"Failed to download file: HTTP {response.status}")

            # Create a temporary directory (automatically cleaned up)
            with tempfile.TemporaryDirectory() as tmpdir:
                tar_path = os.path.join(tmpdir, "corpus.tar.gz")

                # Save the downloaded file
                async with aiofiles.open(tar_path, "wb") as f:
                    await f.write(await response.read())

                # Extract the tar.gz file
                with tarfile.open(tar_path, "r:gz") as tar:
                    tar.extractall(path=tmpdir, filter='tar')

                # Look for the extracted directory with the original name
                extracted_dir = os.path.join(tmpdir, original_filename)
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
                    # each line is tab-separated into word-id, word, occurrences
                    # word-ids until 100 are usually special characters
                    for line in contents.splitlines():
                        parts = line.strip().split("\t")
                        if len(parts) >= 2:
                            result.append(parts[1])

                return result

async def main():
    words_10k = await extract_words('https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_10K.tar.gz')
    words_100k = await extract_words('https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_100K.tar.gz')
    words_1m = await extract_words('https://downloads.wortschatz-leipzig.de/corpora/deu_wikipedia_2021_1M.tar.gz')

    result_10k = analyze(words_10k, token_width=1)
    result_100k = analyze(words_100k, token_width=1)
    result_1m = analyze(words_1m, token_width=1)
    print('done')

if __name__ == '__main__':
    asyncio.run(main())
