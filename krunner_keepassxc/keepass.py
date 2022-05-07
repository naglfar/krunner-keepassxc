#!/bin/env python3
import time
import os
import subprocess
import random
from typing import Dict, List, Optional, Callable, TypedDict
import dbus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

from .dhcrypto import dhcrypto

Entry = TypedDict('Entry', {
	'label': str,
	'path': dbus.ObjectPath,
	'attributes': Dict[str, str]
})

class KeepassPasswords:

	BUS_NAMES: List[str] = [
		'org.keepassxc.KeePassXC.MainWindow',
		'org.freedesktop.secrets'
	]

	bus: dbus._dbus.SessionBus
	_session: Optional[str]
	last_check: Optional[float]
	_entries: List[Entry]

	mainloop: dbus.mainloop.NativeMainLoop
	loop: dbus.mainloop

	crypto: dhcrypto

	def __init__(self, mainloop = None):

		if mainloop:
			self.mainloop = mainloop
			self.loop = None
		else:
			self.mainloop = DBusGMainLoop(set_as_default=True)
			self.loop = GLib.MainLoop()

		self.bus = dbus.SessionBus(mainloop=self.mainloop)

		self._session = None
		self.last_check = None

		self._entries = []

		self.crypto = dhcrypto()

		self.__BUS_NAME = None

	@property
	def session(self) -> Optional[str]:

		if not self._session:
			secrets = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets')
			iface = dbus.Interface(secrets, 'org.freedesktop.Secret.Service')

			if not self.crypto.active:
				_output, session_path = iface.OpenSession('plain', '')
			else:
				server_pubkey, session_path = iface.OpenSession('dh-ietf1024-sha256-aes128-cbc-pkcs7', dbus.ByteArray(self.crypto.pubkey_as_bytes()))
				self.crypto.set_server_public_key(server_pubkey)

			self._session = session_path

		return self._session

	def clear_session(self):
		self._session = None

	@property
	def BUS_NAME(self):
		if not self.__BUS_NAME:
			self.__BUS_NAME = self.find_bus_name()

		return self.__BUS_NAME

	def find_bus_name(self):
		for bus_name in self.BUS_NAMES:
			try:
				secrets = self.bus.get_object(bus_name, '/org/freedesktop/secrets')
				return bus_name
			except dbus.exceptions.DBusException as e:
				pass
		return None

	def is_keepass_installed(self):
		return subprocess.call(['which', "keepassxc"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def open_keepass(self):
		subprocess.Popen(['keepassxc'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setpgrp)

	def update_properties(self):
		now = time.time()
		# try to fetch every 5s if no entries, 30s when cached entries exist
		if not self.last_check or (len(self._entries) == 0 and now - 5 > self.last_check) or ((now - 30 * 1 ) > self.last_check):
			self.last_check = now
			self.fetch_data()

	@property
	def entries(self) -> List[Entry]:
		self.update_properties()
		return self._entries

	def fetch_data(self):

		entries: List[Entry] = []

		try:
			# find collections
			secrets = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets')
			iface = dbus.Interface(secrets, 'org.freedesktop.DBus.Properties')
			collections = iface.GetAll('org.freedesktop.Secret.Service')

			for collection_path in collections.get('Collections'):

				# find collection entries
				collection = self.bus.get_object(self.BUS_NAME, collection_path)
				#print(passwords.Introspect())
				iface = dbus.Interface(collection, 'org.freedesktop.DBus.Properties')
				items = iface.GetAll('org.freedesktop.Secret.Collection')

				for item_path in items.get('Items'):
					password = self.bus.get_object(self.BUS_NAME, item_path)
					iface2 = dbus.Interface(password, 'org.freedesktop.DBus.Properties')
					items = iface2.GetAll('org.freedesktop.Secret.Item')
					label = str(items.get('Label'))

					attr = items.get('Attributes')

					entries.append({
						'label': label,
						'path': item_path,
						'attributes': attr
					})

		except dbus.exceptions.DBusException as e:
			# keepassxc not running	or database closed
			pass

		self._entries = entries

	def clear_cache(self):
		self._entries = []

	def get_attribute(self, path: dbus.ObjectPath, attribute_name: str) -> str:
		attribute_value = ""
		try:
			entry = next(filter(lambda e: e["path"] == path, self.entries))
			if entry:
				return entry["attributes"][attribute_name]

		except KeyError:
			pass

		return attribute_value

	def get_url(self, path: dbus.ObjectPath) -> str:
		return self.get_attribute(path, 'URL')

	def get_username(self, path: dbus.ObjectPath) -> str:
		return self.get_attribute(path, 'UserName')

	def get_secret_impl(self, iface, cb: Callable[[str], None] = None, recursed = False):

		result = None
		try:
			result = iface.GetSecret(str(self.session))
		except dbus.exceptions.DBusException as e:
			if e.args[0] == 'org.freedesktop.Secret.Error.NoSession' and not recursed:
				self.clear_session()
				return self.get_secret_impl(iface, cb, True)
			else:
				print(e)


		if result:
			if not self.crypto.active:
				secret = bytes(result[2]).decode('utf-8')
			else:
				secret = self.crypto.decrypt_message(result)

			if cb:
				cb(secret)

			return secret

		return ''


	# TODO: find a way around using callbacks for async prompt waiting
	def get_secret(self, path: dbus.ObjectPath, cb: Callable[[str], None] = None) -> str:
		password = self.bus.get_object(self.BUS_NAME, path)
		iface = dbus.Interface(password, 'org.freedesktop.Secret.Item')

		result = None
		locked = False
		try:
			locked = iface.Locked()
		except dbus.exceptions.DBusException as e:
			pass

		if locked:

			secrets = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets')
			iface2 = dbus.Interface(secrets, 'org.freedesktop.Secret.Service')
			unlocked, prompt_path = iface2.Unlock([password])
			prompt = self.bus.get_object(self.BUS_NAME, prompt_path)

			# nothing left to unlock
			if prompt_path == '/':
				return self.get_secret_impl(iface, cb)

			else:
				iface3 = dbus.Interface(prompt, 'org.freedesktop.Secret.Prompt')

				def handler_function(dismissed: bool, passwordPath: str):
					nonlocal result

					if self.loop:
						self.loop.quit()

					if not dismissed:
						self.get_secret_impl(iface, cb)


				self.bus.add_signal_receiver(handler_function, 'Completed', 'org.freedesktop.Secret.Prompt', 'org.keepassxc.KeePassXC.MainWindow', prompt_path)
				iface3.Prompt("")

				if self.loop:
					self.loop.run()
				else:
					return ''

			return ''

		else:
			return self.get_secret_impl(iface, cb)
