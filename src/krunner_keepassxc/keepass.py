#!/bin/env python3
import asyncio
import time
import os
import subprocess
from typing import Dict, List, Optional, Callable, cast
from cgitb import handler
import dbus
import pyotp

from .dhcrypto import dhcrypto
from .types import Config, Entry

from dbus_fast.aio import MessageBus
from dbus_fast import Variant

class KeepassPasswords:

	BUS_NAMES: List[str] = [
		'org.keepassxc.KeePassXC.MainWindow',
		'org.freedesktop.secrets'
	]

	BUS_NAME = 'org.keepassxc.KeePassXC.MainWindow'

	bus: None
	_session: Optional[str]
	last_check: Optional[float]
	_entries: List[Entry]
	_otp: bool = False

	config: Config

	crypto: dhcrypto

	def __init__(self, config = {}, bus = None):

		self.bus = None
		if bus:
			self.bus = bus

		self._session = None
		self.last_check = None

		self._entries = []

		self.crypto = dhcrypto()

		self.__BUS_NAME = None

		self.config = config

	async def async_init(self):
		if self.bus is None:
			self.bus = await MessageBus().connect()

		return self

	def __await__(self):
		return self.async_init().__await__()

	async def get_session(self) -> Optional[str]:

		if not self._session:
			introspection = await self.bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			secrets = self.bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			iface = secrets.get_interface('org.freedesktop.Secret.Service')

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

	def clear_session(self):
		self._session = None

	def is_keepass_installed(self):
		return subprocess.call(['which', "keepassxc"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def open_keepass(self):
		subprocess.Popen(['keepassxc'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setpgrp)

	async def update_properties(self):
		now = time.time()
		# try to fetch every 5s if no entries, 30s when cached entries exist
		if not self.last_check or (len(self._entries) == 0 and now - 5 > self.last_check) or ((now - 30 * 1 ) > self.last_check):
			self.last_check = now
			await self.fetch_data()

	async def get_entries(self):
		await self.update_properties()
		return self._entries

	@property
	def otp(self) -> bool:
		return self._otp

	async def fetch_data(self):

		entries: List[Entry] = []
		self._otp = False

		try:

			# find collections
			introspection = await self.bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			proxy_object = self.bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			properties_iface = proxy_object.get_interface('org.freedesktop.DBus.Properties')
			properties_variant = await properties_iface.call_get_all('org.freedesktop.Secret.Service')
			collections = {k: v.value for k, v in properties_variant.items()}
			# print([1, collections])

			for collection_path in collections.get('Collections'):

				# find collection entries
				introspection = await self.bus.introspect(self.BUS_NAME, collection_path)
				collection = self.bus.get_proxy_object(self.BUS_NAME, collection_path, introspection)
				collection_iface = collection.get_interface('org.freedesktop.DBus.Properties')
				properties_variant = await collection_iface.call_get_all('org.freedesktop.Secret.Collection')
				items = {k: v.value for k, v in properties_variant.items()}
				# print([2, items])

				for item_path in items.get('Items'):

					introspection = await self.bus.introspect(self.BUS_NAME, item_path)
					item = self.bus.get_proxy_object(self.BUS_NAME, item_path, introspection)
					item_iface = item.get_interface('org.freedesktop.DBus.Properties')
					properties_variant = await item_iface.call_get_all('org.freedesktop.Secret.Item')
					properties = {k: v.value for k, v in properties_variant.items()}

					label = str(properties.get('Label'))
					attr = properties.get('Attributes')
					# print(attr)

					entries.append({
						'label': label,
						'path': item_path,
						'attributes': attr
					})

					try:
						if attr['otp']:
							self._otp = True

							if "totp_as_extra_entry" in self.config and self.config["totp_as_extra_entry"].lower() != 'false':
								entries.append({
									'label': label + ' TOTP',
									'path': item_path + ':totp',
									'attributes': attr
								})

					except KeyError as e:
						# print(e)
						pass

		except dbus.exceptions.DBusException as e:
			# keepassxc not running	or database closed
			print(e)

		self._entries = entries

	def clear_cache(self):
		self._entries = []

	async def get_attribute(self, path: dbus.ObjectPath, attribute_name: str) -> str:
		attribute_value = ""
		try:
			entry = next(filter(lambda e: e["path"] == path, await self.get_entries()))
			if entry:
				return entry["attributes"][attribute_name]

		except KeyError:
			pass

		return attribute_value

	async def get_url(self, path: dbus.ObjectPath) -> str:
		return await self.get_attribute(path, 'URL')

	async def get_username(self, path: dbus.ObjectPath) -> str:
		return await self.get_attribute(path, 'UserName')

	async def get_totp(self, path: dbus.ObjectPath) -> str:
		totp = ""
		attr = await self.get_attribute(path, 'otp')
		if attr:
			try:
				totp = cast(pyotp.TOTP, pyotp.parse_uri(attr)).now()
			except:
				pass

		return totp

	async def get_secret(self, path: dbus.ObjectPath) -> str:

		introspection = await self.bus.introspect(self.BUS_NAME, path)
		proxy_object = self.bus.get_proxy_object(self.BUS_NAME, path, introspection)

		path_iface = proxy_object.get_interface('org.freedesktop.Secret.Item')

		if await path_iface.get_locked():

			introspection = await self.bus.introspect(self.BUS_NAME, '/org/freedesktop/secrets')
			proxy_object = self.bus.get_proxy_object(self.BUS_NAME, '/org/freedesktop/secrets', introspection)
			iface = proxy_object.get_interface('org.freedesktop.Secret.Service')

			unlocked, prompt_path = await iface.call_unlock([path])

			prompt_introspection = await self.bus.introspect(self.BUS_NAME, prompt_path)
			prompt = self.bus.get_proxy_object(self.BUS_NAME, prompt_path, prompt_introspection)
			prompt_iface = prompt.get_interface('org.freedesktop.Secret.Prompt')

			loop = asyncio.get_running_loop()
			future = loop.create_future()

			# nothing left to unlock
			if unlocked or prompt_path == '/':
				pass

			else:
				def handler_function(dismissed: bool, passwordPath: str):
					future.set_result(not dismissed)

				prompt_iface.on_completed(handler_function)

				await prompt_iface.call_prompt("")

				if not await future:
					return ''

		result = ''

		try:
			session = await self.get_session()
			result = await path_iface.call_get_secret(str(session))
		except dbus.exceptions.DBusException as e:
			if e.args[0] == 'org.freedesktop.Secret.Error.NoSession':
				# retry with a new session
				try:
					self.clear_session()
					session = await self.get_session()
					result = await path_iface.call_get_secret(str(session))
				except dbus.exceptions.DBusException as e:
					print(e)
			else:
				print(e)


		if result:
			if not self.crypto.active:
				secret = bytes(result[2]).decode('utf-8')
			else:
				secret = self.crypto.decrypt_message(result)

			return secret

		return ''

