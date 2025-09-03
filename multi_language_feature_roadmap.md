## Multi-Language Feature Roadmap
- [x] Add field to SQLAlchemy models (comma-separated string of languages).
  - [x] `WordCacheModel.language`
  - [x] `ServerConfigModel.languages`
- [x] Alembic upgrade/downgrade.
- [x] Add field to Pydantic models (read/write from/to comma-separated string from list).
  - [x] `WordCache.language`
  - [x] `ServerConfig.languages`
  - [x] Accordingly manage reading and updating the database.
- [x] `pyproject.toml` and `requirements.txt` update for `unidecode` library.
- [x] Filter input via `unidecode`, then match with the existing regex.
- [x] Search `WordCache` for all languages in `ServerConfig.languages`.
- [x] **Keep accents** when comparing equality of last and first letters.
- [x] Separate API query for each language, started concurrently.
  - [x] Proceed if just one language returns True, BUT ...
  - [x] ... check the remaining languages to add to whitelist.
- [x] **Special check:** Add a word to the English word cache IF and ONLY IF the word is composed of letters of the
English alphabet. This is because many words in other languages have `en.wiktionary` entries.
- [x] Use `unidecode` in karma calculations.
- [x] **Skip** **default blacklists** if unidecode(word) ≠ input word.
- [ ] ~~Modify message sent on messing up to include the server languages.~~
- [x] Commands
  - [x] Server Manager Commands
    - [x] Add/remove languages
  - [x] User Commands
    - [x] ~~Add language option to `/check_word` (defaults to English)~~ (see notes below)
    - [x] Modify `/check_word` to correctly match the pattern, default blacklists,
word cache, and then start a query if required.
    - [x] Let users view the languages allowed in the server.

## Notes
- `/check_word` will default to the languages enabled in the guild it is being run in.
- No language field for server-specific blacklist, whitelist and used_words schema, 
as it doesn't matter the language as long as the word is found in the list/schema.
