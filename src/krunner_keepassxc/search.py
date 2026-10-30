"""Search and ranking of the KeePassXC entries, shared by the krunner service and the CLI"""
import re
from urllib.parse import urlsplit

from .types import Entry

# Path contains the group and the title of the entry
SEARCHED_ATTRIBUTES = ('Path', 'URL', 'UserName')

# Ranking, highest first. Entries are grouped by how many words of the query are in the title (or
# start a part of the URL's host name, which identifies the service just as well): all of them,
# some (the others are in the group, user name or URL path, e.g. "github stefan" for the title
# GitHub with the user name stefan), none. Within each group the tiers below are applied to
# these words.
BONUS_ALL_IN_TITLE = 200
BONUS_SOME_IN_TITLE = 100

SCORE_EXACT = 100        # title is the query
SCORE_PREFIX = 80        # title starts with the query
SCORE_WORD_START = 60    # every word of the query starts a word of the title ("mail" in "Work Mail", "git" in "MyGitHub")
SCORE_HOST = 50          # every word of the query starts a part of the URL's host name ("github" for https://www.github.com/...)
SCORE_CONTAINS = 40      # title contains every word of the query, also inside words
SCORE_OTHER = 20         # only found in the path (group), URL or user name

_WORD = re.compile(r'[^\W_]+')
_CAMEL_CASE = re.compile(r'[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+')


def _words(text: str) -> list[str]:
	"""lower case words of a title, also split at camel case ("MyGitHub" -> my, git, hub)"""
	words: list[str] = []
	for word in _WORD.findall(text):
		parts = _CAMEL_CASE.findall(word)
		words.extend(part.lower() for part in (parts or [word]))
		if len(parts) > 1:
			words.append(word.lower())
	return words


def _host_parts(url: str) -> list[str]:
	"""parts of the host name without "www", also for URLs without scheme ("github.com/login")"""
	if not url:
		return []
	host = urlsplit(url if '//' in url else '//' + url).hostname or ''
	return [part for part in host.split('.') if part and part != 'www']


def _every_word_starts(words: list[str], candidates: list[str]) -> bool:
	return bool(candidates) and all(any(candidate.startswith(word) for candidate in candidates) for word in words)


def _title_score(entry: Entry, words: list[str]) -> int:
	label = entry['label'].lower()
	query = ' '.join(words)
	if label == query:
		return SCORE_EXACT
	if label.startswith(query):
		return SCORE_PREFIX
	if _every_word_starts(words, _words(entry['label'])):
		return SCORE_WORD_START
	if _every_word_starts(words, _host_parts(entry['attributes'].get('URL', ''))):
		return SCORE_HOST
	return SCORE_CONTAINS


def score(entry: Entry, query: str) -> int:
	"""how well an entry, that matched the query, fits it (see the SCORE_ constants)"""
	words = query.lower().split()
	label = entry['label'].lower()
	host = _host_parts(entry['attributes'].get('URL', ''))
	in_title = [word for word in words if word in label or any(part.startswith(word) for part in host)]
	if not in_title:
		return SCORE_OTHER
	bonus = BONUS_ALL_IN_TITLE if len(in_title) == len(words) else BONUS_SOME_IN_TITLE
	return bonus + _title_score(entry, in_title)


def _matches(entry: Entry, words: list[str]) -> bool:
	"""every word occurs in one of the searched attributes, not necessarily the same one"""
	values = [entry['attributes'].get(attribute, '').lower() for attribute in SEARCHED_ATTRIBUTES]
	return all(any(word in value for value in values) for word in words)


def _in_one_attribute(entry: Entry, words: list[str]) -> bool:
	return any(
		all(word in entry['attributes'].get(attribute, '').lower() for word in words)
		for attribute in SEARCHED_ATTRIBUTES
	)


def search(entries: list[Entry], query: str) -> list[Entry]:
	"""
	Entries where every word of the query occurs in one of the searched attributes, case insensitive.

	Best matches first (see score()); with the same score, entries having all words in one
	attribute come first, then alphabetically by title.
	"""
	words = query.lower().split()
	found = [entry for entry in entries if _matches(entry, words)]
	found.sort(key=lambda entry: (
		-score(entry, query),
		not _in_one_attribute(entry, words),
		entry['label'].casefold(),
		entry['label'],
	))
	return found
