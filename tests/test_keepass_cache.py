import asyncio
import unittest
from typing import cast

from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.types import Entry


class SlowKeepass(KeepassPasswords):
	"""fetch_data replaced by a slow fake, counts the fetches"""

	def __init__(self, delay: float = 0.2) -> None:
		super().__init__()
		self.delay = delay
		self.fetches = 0

	async def fetch_data(self) -> None:
		self.fetches += 1
		await asyncio.sleep(self.delay)
		self._entries = [cast(Entry, {'label': f'entry {self.fetches}', 'path': '/1', 'attributes': {}})]


class CacheTests(unittest.IsolatedAsyncioTestCase):

	async def test_concurrent_calls_share_the_first_fetch(self) -> None:
		# krunner: Actions and one Match per keystroke arrive at the same time after activation
		kp = SlowKeepass()
		results = await asyncio.gather(kp.update_properties(), kp.get_entries(), kp.get_entries())
		self.assertEqual(kp.fetches, 1)
		self.assertEqual([len(r) for r in results[1:]], [1, 1])

	async def test_refresh_with_cached_entries_runs_in_background(self) -> None:
		kp = SlowKeepass(delay=0.5)
		await kp.get_entries()
		assert kp.last_check is not None
		kp.last_check -= 31  # refresh due

		start = asyncio.get_running_loop().time()
		entries = await kp.get_entries()
		self.assertLess(asyncio.get_running_loop().time() - start, 0.1)
		self.assertEqual(entries[0]['label'], 'entry 1')  # cached entries, no waiting

		await asyncio.sleep(0.6)
		self.assertEqual(kp.fetches, 2)
		self.assertEqual((await kp.get_entries())[0]['label'], 'entry 2')

	async def test_cancelled_caller_does_not_abort_the_fetch(self) -> None:
		kp = SlowKeepass()
		first = asyncio.create_task(kp.get_entries())
		await asyncio.sleep(0.05)
		second = asyncio.create_task(kp.get_entries())
		await asyncio.sleep(0)
		first.cancel()
		self.assertEqual(len(await second), 1)
		self.assertEqual(kp.fetches, 1)


if __name__ == '__main__':
	unittest.main()
