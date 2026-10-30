import asyncio
import contextlib
import io
import unittest
from typing import Any, cast

from dbus_fast.aio import MessageBus

from krunner_keepassxc.autotype import AutotypeError
from krunner_keepassxc.runner import KeepassRunner
from krunner_keepassxc.types import Config, Entry

# the dbus_method decorator wraps the methods, the originals are still reachable
match = KeepassRunner.Match.__wrapped__  # type: ignore[attr-defined]
run = KeepassRunner.Run.__wrapped__  # type: ignore[attr-defined]


def entry(label: str, user: str = '', otp: bool = False) -> Entry:
	return cast(Entry, {
		'label': label,
		'path': f'/org/freedesktop/secrets/collection/x/{label.replace(" ", "_")}',
		'attributes': {'Path': f'Root/{label}', 'URL': '', 'UserName': user, **({'otp': 'otpauth://x'} if otp else {})},
	})


class FakeKeepass:
	BUS_NAME = 'org.keepassxc.KeePassXC.MainWindow'

	def __init__(self, entries: list[Entry], installed: bool = True) -> None:
		self.entries = entries
		self.installed = installed
		self.opened = False

	async def get_entries(self) -> list[Entry]:
		return self.entries

	def is_keepass_installed(self) -> bool:
		return self.installed

	def open_keepass(self) -> None:
		self.opened = True

	def _attribute(self, path: str, name: str) -> str:
		return next(e['attributes'].get(name, '') for e in self.entries if e['path'] == path)

	async def get_username(self, path: str) -> str:
		return self._attribute(path, 'UserName')

	async def get_secret(self, path: str) -> str:
		return 'secret of ' + path.rsplit('/', 1)[1]

	async def get_totp(self, path: str) -> str:
		return '123456' if self._attribute(path, 'otp') else ''


class FakeClipboard:

	def __init__(self, can_clip: bool = True) -> None:
		self.can_clip = can_clip
		self.checked = 0
		self.copied: list[str] = []

	async def check_executables(self) -> None:
		self.checked += 1

	async def copy(self, text: str, primary: bool = False) -> None:
		self.copied.append(text)

	async def clear(self, primary: bool = False) -> None:
		self.copied.append('<cleared>')


class FakeAutotype:

	def __init__(self, fail: bool = False) -> None:
		self.fail = fail
		self.typed: list[str] = []

	async def type(self, text: str) -> None:
		if self.fail:
			raise AutotypeError('no portal')
		self.typed.append(text)


def make_runner(entries: list[Entry] | None = None, installed: bool = True, can_clip: bool = True,
		**config: object) -> KeepassRunner:
	settings = {'trigger': '', 'max_entries': 5, 'icon': 'object-unlocked', 'autotype': 'false',
		'totp_as_extra_entry': 'True', 'clipboard_clear_delay': 0, **config}
	runner = KeepassRunner(cast(Config, settings), cast(MessageBus, object()))
	runner.kp = cast(Any, FakeKeepass(entries or [], installed))
	runner.cp = cast(Any, FakeClipboard(can_clip))
	return runner


def texts(matches: list) -> list[str]:
	return [m[1] for m in matches]


class MatchTests(unittest.IsolatedAsyncioTestCase):

	async def test_queries_up_to_two_characters_are_ignored(self) -> None:
		runner = make_runner([entry('Mail')])
		self.assertEqual(await match(runner, 'ma'), [])
		self.assertEqual(texts(await match(runner, 'mai')), ['Mail'])

	async def test_trigger_word(self) -> None:
		# read_config() appends the space to a configured trigger
		runner = make_runner([entry('Mail')], trigger='kp ')
		self.assertEqual(await match(runner, 'mail'), [])
		self.assertEqual(texts(await match(runner, 'kp mail')), ['Mail'])

	async def test_results_ranking_limit_and_properties(self) -> None:
		entries = [entry(f'Git {i}', user=f'user{i}') for i in range(7)] + [entry('Other')]
		runner = make_runner(entries, max_entries=3)
		matches = await match(runner, 'git')
		self.assertEqual(texts(matches), ['Git 0', 'Git 1', 'Git 2'])
		path, _text, icon, category_relevance, relevance, properties = matches[1]
		self.assertEqual(path, entries[1]['path'])
		self.assertEqual(icon, 'object-unlocked')
		self.assertEqual(category_relevance, 100)
		self.assertAlmostEqual(relevance, 0.9)
		self.assertEqual(properties['subtext'].value, 'user1')
		self.assertEqual(properties['category'].value, 'KeePassXC: copy to clipboard')

	async def test_no_clipboard(self) -> None:
		runner = make_runner([entry('Mail')], can_clip=False)
		matches = await match(runner, 'mail')
		self.assertEqual(texts(matches), ['No clipboard available'])
		self.assertEqual(cast(FakeClipboard, runner.cp).checked, 1)  # tries to find a clipboard again
		self.assertEqual(matches[0][5]['category'].value, 'KeePassXC: copy to clipboard')

	async def test_keepassxc_not_installed(self) -> None:
		runner = make_runner([], installed=False)
		self.assertEqual(texts(await match(runner, 'mail')), ['KeepassXC does not seem to be installed'])

	async def test_database_locked_offers_to_open_keepassxc(self) -> None:
		runner = make_runner([])
		matches = await match(runner, 'mail')
		self.assertEqual(texts(matches), ['No passwords or database locked'])
		self.assertEqual(matches[0][5]['subtext'].value, 'Open KeepassXC')

		await run(runner, '', '')
		self.assertTrue(cast(FakeKeepass, runner.kp).opened)
		# only once, the next empty Run doesn't open it again
		cast(FakeKeepass, runner.kp).opened = False
		await run(runner, '', '')
		self.assertFalse(cast(FakeKeepass, runner.kp).opened)


class RunTests(unittest.IsolatedAsyncioTestCase):

	async def asyncSetUp(self) -> None:
		self.entries = [entry('Mail', user='stefan', otp=True), entry('Shop', user='alice')]
		self.runner = make_runner(self.entries)
		self.clipboard = cast(FakeClipboard, self.runner.cp)

	async def test_default_action_copies_the_password(self) -> None:
		await run(self.runner, self.entries[0]['path'], '')
		self.assertEqual(self.clipboard.copied, ['secret of Mail'])

	async def test_user_action_copies_the_username(self) -> None:
		await run(self.runner, self.entries[1]['path'], 'user')
		self.assertEqual(self.clipboard.copied, ['alice'])

	async def test_totp_action_and_totp_entries(self) -> None:
		await run(self.runner, self.entries[0]['path'], 'totp')
		# the extra TOTP entries carry the action in their id
		await run(self.runner, self.entries[0]['path'] + ':totp', '')
		self.assertEqual(self.clipboard.copied, ['123456', '123456'])

	async def test_nothing_is_copied_without_totp(self) -> None:
		await run(self.runner, self.entries[1]['path'], 'totp')
		self.assertEqual(self.clipboard.copied, [])

	async def test_autotype(self) -> None:
		autotype = FakeAutotype()
		self.runner.autotype = cast(Any, autotype)
		await run(self.runner, self.entries[0]['path'], '')
		await asyncio.gather(*self.runner._tasks)
		self.assertEqual(autotype.typed, ['secret of Mail'])
		self.assertEqual(self.clipboard.copied, [])

	async def test_autotype_failure_falls_back_to_the_clipboard(self) -> None:
		self.runner.autotype = cast(Any, FakeAutotype(fail=True))
		with contextlib.redirect_stdout(io.StringIO()) as output:
			await run(self.runner, self.entries[0]['path'], 'user')
			await asyncio.gather(*self.runner._tasks)
		self.assertEqual(self.clipboard.copied, ['stefan'])
		self.assertIn('autotype failed', output.getvalue())

	async def test_clipboard_is_cleared_after_the_delay(self) -> None:
		self.runner.config['clipboard_clear_delay'] = 1
		await run(self.runner, self.entries[0]['path'], '')
		self.assertTrue(self.runner.busy)
		await asyncio.sleep(1.1)
		self.assertEqual(self.clipboard.copied, ['secret of Mail', '<cleared>'])
		self.assertFalse(self.runner.busy)


if __name__ == '__main__':
	unittest.main()
