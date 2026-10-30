"""Search and ranking of the KeePassXC entries, shared by the krunner service and the CLI"""
import re
import unicodedata
from itertools import product
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
_UMLAUTS_SPELLED_OUT = str.maketrans({'ä': 'ae', 'ö': 'oe', 'ü': 'ue'})


# Comparisons ignore case and accents ("Müller", "MÜLLER" -> muller, "Café" -> cafe, "Straße" -> strasse).
# German umlauts are additionally compared spelled out ("Müller" -> mueller), in both directions:
# "muller", "müller" and "mueller" find "Müller", "günther" also finds "Guenther". A query is only
# spelled out where it contains an umlaut, "ue" is never read as "ü" ("que" must not find "Quintus").

# a word of the query: its alternative comparable forms
Word = tuple[str, ...]


def _strip_accents(text: str) -> str:
	return ''.join(char for char in unicodedata.normalize('NFKD', text) if not unicodedata.combining(char))


def _forms(text: str) -> tuple[str, ...]:
	"""the comparable forms of a text: accents removed and, if different, umlauts spelled out"""
	folded = text.casefold()
	plain = _strip_accents(folded)
	spelled_out = _strip_accents(folded.translate(_UMLAUTS_SPELLED_OUT))
	return (plain,) if spelled_out == plain else (plain, spelled_out)


def _query_words(query: str) -> list[Word]:
	return [_forms(word) for word in query.split()]


def _occurs(word: Word, texts: tuple[str, ...] | list[str]) -> bool:
	return any(form in text for form in word for text in texts)


def _words(text: str) -> list[str]:
	"""comparable words of a title, also split at camel case ("MyGitHub" -> my, git, hub, mygithub)"""
	words: list[str] = []
	for word in _WORD.findall(text):
		parts = _CAMEL_CASE.findall(word)
		for part in (parts or [word]):
			words.extend(_forms(part))
		if len(parts) > 1:
			words.extend(_forms(word))
	return words


def _host_parts(url: str) -> list[str]:
	"""comparable parts of the host name without "www", also for URLs without scheme ("github.com/login")"""
	if not url:
		return []
	host = urlsplit(url if '//' in url else '//' + url).hostname or ''
	return [form for part in host.split('.') if part and part != 'www' for form in _forms(part)]


def _starts(word: Word, candidates: list[str]) -> bool:
	return any(candidate.startswith(form) for form in word for candidate in candidates)


def _every_word_starts(words: list[Word], candidates: list[str]) -> bool:
	return bool(candidates) and all(_starts(word, candidates) for word in words)


def _title_score(entry: Entry, words: list[Word]) -> int:
	labels = _forms(entry['label'])
	# every combination of the words' forms, at most a few as only words with umlauts have two
	queries = {' '.join(combination) for combination in product(*words)}
	if any(query in labels for query in queries):
		return SCORE_EXACT
	if any(label.startswith(query) for label in labels for query in queries):
		return SCORE_PREFIX
	if _every_word_starts(words, _words(entry['label'])):
		return SCORE_WORD_START
	if _every_word_starts(words, _host_parts(entry['attributes'].get('URL', ''))):
		return SCORE_HOST
	return SCORE_CONTAINS


def score(entry: Entry, query: str) -> int:
	"""how well an entry, that matched the query, fits it (see the SCORE_ and BONUS_ constants)"""
	words = _query_words(query)
	labels = _forms(entry['label'])
	host = _host_parts(entry['attributes'].get('URL', ''))
	in_title = [word for word in words if _occurs(word, labels) or _starts(word, host)]
	if not in_title:
		return SCORE_OTHER
	bonus = BONUS_ALL_IN_TITLE if len(in_title) == len(words) else BONUS_SOME_IN_TITLE
	return bonus + _title_score(entry, in_title)


def _attribute_forms(entry: Entry) -> list[tuple[str, ...]]:
	return [_forms(entry['attributes'].get(attribute, '')) for attribute in SEARCHED_ATTRIBUTES]


def _matches(attributes: list[tuple[str, ...]], words: list[Word]) -> bool:
	"""every word occurs in one of the searched attributes, not necessarily the same one"""
	return all(any(_occurs(word, forms) for forms in attributes) for word in words)


def _in_one_attribute(attributes: list[tuple[str, ...]], words: list[Word]) -> bool:
	return any(all(_occurs(word, forms) for word in words) for forms in attributes)


def search(entries: list[Entry], query: str) -> list[Entry]:
	"""
	Entries where every word of the query occurs in one of the searched attributes, ignoring case
	and accents.

	Best matches first (see score()); with the same score, entries having all words in one
	attribute come first, then alphabetically by title.
	"""
	words = _query_words(query)
	found = []
	for entry in entries:
		attributes = _attribute_forms(entry)
		if _matches(attributes, words):
			found.append((
				-score(entry, query),
				not _in_one_attribute(attributes, words),
				# alphabetical, umlauts and accents like their base letter ("Ärzte" among the a's)
				_strip_accents(entry['label'].casefold()),
				entry['label'].casefold(),
				entry['label'],
				entry,
			))
	found.sort(key=lambda item: item[:5])
	return [item[5] for item in found]
