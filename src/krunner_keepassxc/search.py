"""Search and ranking of the KeePassXC entries, shared by the krunner service and the CLI"""
import re
from urllib.parse import urlsplit

from .types import Entry

# Path contains the group and the title of the entry
SEARCHED_ATTRIBUTES = ('Path', 'URL', 'UserName')

# ranking, highest first
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


def score(entry: Entry, query: str) -> int:
	"""how well an entry, that matched the query, fits it (see the SCORE_ constants)"""
	query = query.lower().strip()
	words = query.split()
	label = entry['label'].lower()
	if not words:
		return SCORE_OTHER
	if label == query:
		return SCORE_EXACT
	if label.startswith(query):
		return SCORE_PREFIX
	if _every_word_starts(words, _words(entry['label'])):
		return SCORE_WORD_START
	if _every_word_starts(words, _host_parts(entry['attributes'].get('URL', ''))):
		return SCORE_HOST
	if all(word in label for word in words):
		return SCORE_CONTAINS
	return SCORE_OTHER


def search(entries: list[Entry], query: str) -> list[Entry]:
	"""
	Entries where all words of the query occur in one of the searched attributes, case insensitive.

	Best matches first (see score()), alphabetically by title within the same score.
	"""
	words = query.lower().split(' ')
	found = [
		entry for entry in entries
		if any(
			all(word in entry['attributes'].get(attribute, '').lower() for word in words)
			for attribute in SEARCHED_ATTRIBUTES
		)
	]
	found.sort(key=lambda entry: (-score(entry, query), entry['label'].casefold(), entry['label']))
	return found
