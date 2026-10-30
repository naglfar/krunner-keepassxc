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

	def test_words_may_be_spread_over_the_attributes(self) -> None:
		entries = [
			entry('Bank', path='Root/Finance/Bank', user='alice'),
		]
		self.assertEqual(labels(search(entries, 'finance bank')), ['Bank'])
		self.assertEqual(labels(search(entries, 'bank finance')), ['Bank'])  # order of the words doesn't matter
		self.assertEqual(labels(search(entries, 'bank alice')), ['Bank'])    # path and user name
		self.assertEqual(search(entries, 'bank bob'), [])                    # every word has to be found

	def test_service_and_account(self) -> None:
		entries = [
			entry('GitHub', user='max'),                               # wrong account: not found
			entry('Stefan GitHub', user='other'),                      # both words start words of the title
			entry('GitHub Enterprise', user='stefan'),                 # title starts with "github", user stefan
			entry('GitHub', user='stefan'),                            # title is "github", user stefan
			entry('Code', url='https://github.com', user='stefan'),    # service only in the host name
			entry('Notes', path='Root/github/Notes', user='stefan'),   # neither in the title nor the host
		]
		# all words in the title first, then the ones with the account in the user name
		self.assertEqual(labels(search(entries, 'github stefan')),
			['Stefan GitHub', 'GitHub', 'GitHub Enterprise', 'Code', 'Notes'])

	def test_words_in_one_attribute_rank_first_on_equal_score(self) -> None:
		entries = [
			entry('A', path='Root/work/A', user='mail'),               # spread over path and user name
			entry('B', path='Root/work mail/B'),                       # both in the path
		]
		self.assertEqual(labels(search(entries, 'work mail')), ['B', 'A'])

	def test_ranking(self) -> None:
		entries = [
			entry('Zulu', path='Root/git/Zulu'),                      # only in the path (group)
			entry('Digital Ocean', path='Root/Digital Ocean'),        # inside a word of the title
			entry('Code', url='https://www.github.com/login'),        # start of the URL's host name
			entry('My GitHub', path='Root/My GitHub'),                # start of a word of the title
			entry('MyGitea', path='Root/MyGitea'),                    # start of a camel case word
			entry('GitLab', path='Root/GitLab'),                      # title starts with the query
			entry('gitea', path='Root/gitea'),                        # title starts with the query
			entry('Git', path='Root/Git'),                            # exact title
			entry('Alpha', path='Root/git/Alpha'),                    # only in the path (group)
		]
		self.assertEqual(labels(search(entries, 'git')), [
			'Git',
			'gitea', 'GitLab',             # alphabetical, case insensitive
			'My GitHub', 'MyGitea',
			'Code',
			'Digital Ocean',
			'Alpha', 'Zulu',
		])

	def test_ranking_with_several_words(self) -> None:
		entries = [
			entry('Mail', path='Root/Work/Mail'),                     # "work" only in the group
			entry('Work Mail Archive', path='Root/Work Mail Archive'),  # title starts with the query
			entry('Mail for Work', path='Root/Mail for Work'),        # both words start words of the title
			entry('Homework Mailbox', path='Root/Homework Mailbox'),  # both words inside the title
		]
		self.assertEqual(labels(search(entries, 'work mail')),
			['Work Mail Archive', 'Mail for Work', 'Homework Mailbox', 'Mail'])

	def test_host_name_variants(self) -> None:
		entries = [
			entry('A', url='mail.google.com/inbox'),                  # without scheme
			entry('B', url='https://www.example.org', path='Root/B mail'),  # only in the path
		]
		self.assertEqual(labels(search(entries, 'mail')), ['A', 'B'])
		self.assertEqual(labels(search(entries, 'google')), ['A'])

	def test_empty_query_returns_everything_sorted(self) -> None:
		entries = [entry('b'), entry('A')]
		self.assertEqual(labels(search(entries, '')), ['A', 'b'])

	def test_missing_attributes_dont_break_the_search(self) -> None:
		broken = cast(Entry, {'label': 'No URL', 'path': '/x', 'attributes': {'Path': 'Root/No URL'}})
		self.assertEqual(labels(search([broken], 'url')), ['No URL'])


if __name__ == '__main__':
	unittest.main()
