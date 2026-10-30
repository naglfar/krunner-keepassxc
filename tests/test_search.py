import unittest
from typing import cast

from krunner_keepassxc.search import search
from krunner_keepassxc.types import Entry


def entry(label: str, path: str = '', url: str = '', user: str = '') -> Entry:
	return cast(Entry, {
		'label': label,
		'path': f'/item/{label}',
		'attributes': {'Path': path or f'Root/{label}', 'URL': url, 'UserName': user},
	})


def labels(entries: list[Entry]) -> list[str]:
	return [e['label'] for e in entries]


class SearchTests(unittest.TestCase):

	def test_searches_path_url_and_username_case_insensitive(self) -> None:
		entries = [
			entry('Mail', path='Root/Work/Mail'),
			entry('Shop', url='https://EXAMPLE.org'),
			entry('Forum', user='Stefan'),
			entry('Other'),
		]
		self.assertEqual(labels(search(entries, 'work')), ['Mail'])
		self.assertEqual(labels(search(entries, 'example')), ['Shop'])
		self.assertEqual(labels(search(entries, 'STEFAN')), ['Forum'])
		self.assertEqual(search(entries, 'nothing'), [])

	def test_all_words_must_occur_in_the_same_attribute(self) -> None:
		entries = [
			entry('Bank', path='Root/Finance/Bank', user='alice'),
		]
		self.assertEqual(labels(search(entries, 'finance bank')), ['Bank'])
		self.assertEqual(labels(search(entries, 'bank finance')), ['Bank'])  # order of the words doesn't matter
		# one word in the path, the other one in the user name: no match
		self.assertEqual(search(entries, 'bank alice'), [])

	def test_ranking(self) -> None:
		entries = [
			entry('Zulu', path='Root/git/Zulu'),           # query only in the path
			entry('My GitHub', path='Root/My GitHub'),     # query inside the label
			entry('GitLab', path='Root/GitLab'),           # label starts with the query
			entry('Gitea', path='Root/Gitea'),             # label starts with the query
			entry('Alpha', path='Root/git/Alpha'),         # query only in the path
		]
		self.assertEqual(labels(search(entries, 'git')), ['GitLab', 'Gitea', 'My GitHub', 'Alpha', 'Zulu'])

	def test_empty_query_returns_everything_sorted(self) -> None:
		entries = [entry('b'), entry('a')]
		self.assertEqual(labels(search(entries, '')), ['a', 'b'])

	def test_missing_attributes_dont_break_the_search(self) -> None:
		broken = cast(Entry, {'label': 'No URL', 'path': '/x', 'attributes': {'Path': 'Root/No URL'}})
		self.assertEqual(labels(search([broken], 'url')), ['No URL'])


if __name__ == '__main__':
	unittest.main()
