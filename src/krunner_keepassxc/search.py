"""Search and ranking of the KeePassXC entries, shared by the krunner service and the CLI"""
from .types import Entry

# Path contains the group and the title of the entry
SEARCHED_ATTRIBUTES = ('Path', 'URL', 'UserName')


def search(entries: list[Entry], query: str) -> list[Entry]:
	"""
	Entries where all words of the query occur in one of the searched attributes, case insensitive.

	Ordered by: label starts with the query, label contains the query, everything else;
	alphabetically by label within each of these groups.
	"""
	query = query.lower()
	words = query.split(' ')
	found = [
		entry for entry in entries
		if any(
			all(word in entry['attributes'].get(attribute, '').lower() for word in words)
			for attribute in SEARCHED_ATTRIBUTES
		)
	]
	found.sort(key=lambda entry: (
		not entry['label'].lower().startswith(query),
		query not in entry['label'].lower(),
		entry['label'],
	))
	return found
