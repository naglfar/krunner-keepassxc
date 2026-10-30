import asyncio
import subprocess
import time
from collections.abc import Generator
from typing import Any, Self, cast

import pyotp
from dbus_fast import DBusError, Variant
from dbus_fast.aio import MessageBus

from .dhcrypto import dhcrypto
from .types import Config, Entry


class KeepassPasswords:
	"""
	Secret Service client for KeePassXC (dbus-fast).

	The proxy interfaces are typed as Any: their call_*/get_*/on_* methods are generated
	from the introspection data at runtime, so mypy can't know them.
	"""

	BUS_NAMES: tuple[str, ...] = (
		'org.keepassxc.KeePassXC.MainWindow',
		'org.freedesktop.secrets'
	)

	BUS_NAME = 'org.keepassxc.KeePassXC.MainWindow'

	bus: MessageBus | None
	_session: str | None
	last_check: float | None
	_entries: list[Entry]
	_otp: bool = False
	_fetch_task: asyncio.Task[None] | None

	config: Config

	crypto: dhcrypto

	def __init__(self, config: Config | None = None, bus: MessageBus | None = None) -> None:

		if config is None:
			config = cast(Config, {})
		self.bus = bus

		self._session = None
		self.last_check = None

		self._entries = []
		self._fetch_task = None

		self.crypto = dhcrypto()

		self.config = config

	async def async_init(self) -> Self:
		if self.bus is None:
			self.bus = await MessageBus().connect()

		return self

	def __await__(self) -> Generator[Any, None, Self]:
		return self.async_init().__await__()

	@property
	def _bus(self) -> MessageBus:
		if self.bus is None:
			raise RuntimeError('not connected to D-Bus, pass a bus or await the KeepassPasswords instance first')
		return self.bus

	async def get_session(self) -> str | None:

		if not self._session:
			introspection = await self._bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			secrets = self._bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			iface: Any = secrets.get_interface('org.freedesktop.Secret.Service')

			if not self.crypto.active:
				_output, session_path = await iface.call_open_session('plain', '')
			else:
				server_pubkey, session_path = await iface.call_open_session(
					'dh-ietf1024-sha256-aes128-cbc-pkcs7',
					Variant('ay', self.crypto.pubkey_as_bytes())
				)
				# print(['!!!', result])
				self.crypto.set_server_public_key(server_pubkey.value)

			self._session = session_path

		return self._session

	def clear_session(self) -> None:
		self._session = None

	def is_keepass_installed(self) -> bool:
		return subprocess.call(['which', "keepassxc"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def open_keepass(self) -> None:
		# own process group, so keepassxc is not affected by signals to this service; output is never read,
		# so don't attach pipes that could fill up and block it
		subprocess.Popen(['keepassxc'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, process_group=0)

	async def update_properties(self) -> None:
		"""
		Refresh the cached entries when due: every 5s while there are none, every 30s otherwise.

		krunner sends its calls concurrently (Actions, one Match per keystroke), so all callers
		share one fetch. While there are no entries yet (e.g. right after D-Bus activation) they
		wait for it instead of getting the still empty list; with cached entries a refresh runs
		in the background and the cache keeps being used meanwhile.
		"""
		if self._fetch_task is None or self._fetch_task.done():
			now = time.time()
			due = (
				not self.last_check
				or (not self._entries and now - 5 > self.last_check)
				or now - 30 > self.last_check
			)
			if not due:
				return
			self.last_check = now
			self._fetch_task = asyncio.create_task(self.fetch_data())
			self._fetch_task.add_done_callback(self._fetch_done)

		if not self._entries:
			# shield: a cancelled krunner call must not abort the fetch the others are waiting for
			await asyncio.shield(self._fetch_task)

	@staticmethod
	def _fetch_done(task: asyncio.Task[None]) -> None:
		# background refreshes are not awaited by anyone, report their errors here
		if not task.cancelled() and task.exception() is not None:
			print(f'fetching the entries failed: {task.exception()!r}', flush=True)

	async def get_entries(self) -> list[Entry]:
		await self.update_properties()
		return self._entries

	@property
	def otp(self) -> bool:
		return self._otp

	async def fetch_data(self) -> None:

		# built locally and assigned at the end, callers keep using the previous state meanwhile
		entries: list[Entry] = []
		otp = False

		try:

			# find collections
			introspection = await self._bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			proxy_object = self._bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			properties_iface: Any = proxy_object.get_interface('org.freedesktop.DBus.Properties')
			properties_variant = await properties_iface.call_get_all('org.freedesktop.Secret.Service')
			collections = {k: v.value for k, v in properties_variant.items()}
			# print([1, collections])

			for collection_path in collections.get('Collections', []):

				# find collection entries
				introspection = await self._bus.introspect(self.BUS_NAME, collection_path)
				collection = self._bus.get_proxy_object(self.BUS_NAME, collection_path, introspection)
				collection_iface: Any = collection.get_interface('org.freedesktop.DBus.Properties')
				properties_variant = await collection_iface.call_get_all('org.freedesktop.Secret.Collection')
				items = {k: v.value for k, v in properties_variant.items()}
				# print([2, items])

				for item_path in items.get('Items', []):

					introspection = await self._bus.introspect(self.BUS_NAME, item_path)
					item = self._bus.get_proxy_object(self.BUS_NAME, item_path, introspection)
					item_iface: Any = item.get_interface('org.freedesktop.DBus.Properties')
					properties_variant = await item_iface.call_get_all('org.freedesktop.Secret.Item')
					properties = {k: v.value for k, v in properties_variant.items()}

					label = str(properties.get('Label'))
					attr = properties.get('Attributes', {})
					# print(attr)

					entries.append({
						'label': label,
						'path': item_path,
						'attributes': attr
					})

					try:
						if attr['otp']:
							otp = True

							if "totp_as_extra_entry" in self.config and self.config["totp_as_extra_entry"].lower() != 'false':
								entries.append({
									'label': label + ' TOTP',
									'path': item_path + ':totp',
									'attributes': attr
								})

					except KeyError:
						# print(e)
						pass

		except DBusError as e:
			# keepassxc not running	or database closed
			print(e)

		self._entries = entries
		self._otp = otp

	def clear_cache(self) -> None:
		self._entries = []

	async def get_attribute(self, path: str, attribute_name: str) -> str:
		attribute_value = ""
		try:
			entry = next(filter(lambda e: e["path"] == path, await self.get_entries()))
			if entry:
				return entry["attributes"][attribute_name]

		except KeyError:
			pass

		return attribute_value

	async def get_url(self, path: str) -> str:
		return await self.get_attribute(path, 'URL')

	async def get_username(self, path: str) -> str:
		return await self.get_attribute(path, 'UserName')

	async def get_totp(self, path: str) -> str:
		totp = ""
		attr = await self.get_attribute(path, 'otp')
		if attr:
			try:
				totp = cast(pyotp.TOTP, pyotp.parse_uri(attr)).now()
			except ValueError as e:
				print(f'invalid TOTP configuration: {e}', flush=True)

		return totp

	async def get_secret(self, path: str) -> str:

		introspection = await self._bus.introspect(self.BUS_NAME, path)
		proxy_object = self._bus.get_proxy_object(self.BUS_NAME, path, introspection)

		path_iface: Any = proxy_object.get_interface('org.freedesktop.Secret.Item')

		if await path_iface.get_locked():

			introspection = await self._bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			proxy_object = self._bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			iface: Any = proxy_object.get_interface('org.freedesktop.Secret.Service')

			unlocked, prompt_path = await iface.call_unlock([path])

			prompt_introspection = await self._bus.introspect(self.BUS_NAME, prompt_path)
			prompt = self._bus.get_proxy_object(self.BUS_NAME, prompt_path, prompt_introspection)
			prompt_iface: Any = prompt.get_interface('org.freedesktop.Secret.Prompt')

			loop = asyncio.get_running_loop()
			future = loop.create_future()

			# nothing left to unlock
			if unlocked or prompt_path == '/':
				pass

			else:
				# Prompt.Completed(b dismissed, v result)
				def handler_function(dismissed: bool, _result: Variant) -> None:
					future.set_result(not dismissed)

				prompt_iface.on_completed(handler_function)

				await prompt_iface.call_prompt("")

				if not await future:
					return ''

		# (session, parameters, value, content type) as returned by GetSecret
		result: Any = None

		try:
			session = await self.get_session()
			result = await path_iface.call_get_secret(str(session))
		except DBusError as e:
			if e.type == 'org.freedesktop.Secret.Error.NoSession':
				# retry with a new session
				try:
					self.clear_session()
					session = await self.get_session()
					result = await path_iface.call_get_secret(str(session))
				except DBusError as retry_error:
					print(retry_error)
			else:
				print(e)


		if result:
			if not self.crypto.active:
				secret = bytes(result[2]).decode('utf-8')
			else:
				secret = self.crypto.decrypt_message(result)

			return secret

		return ''

