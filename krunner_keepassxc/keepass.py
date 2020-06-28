#!/bin/env python3
import time
import os
import subprocess
from typing import Dict, List, Optional
import dbus

from .dhcrypto import dhcrypto

class KeepassPasswords:

	#BUS_NAME: str = 'org.keepassxc.KeePassXC.MainWindow'
	BUS_NAME: str = 'org.freedesktop.secrets'

	bus: dbus._dbus.SessionBus
	_session: Optional[str]
	last_check: Optional[float]
	_labels: List[str]
	_attributes: Dict[str, Dict]
	_entries: Dict[str, dbus.ObjectPath]

	crypto: dhcrypto

	def __init__(self):
		self.bus = dbus.SessionBus()
		self._session = None
		self.last_check = None

		self._labels = []
		self._attributes = {}
		self._entries = {}

		self.crypto = dhcrypto()

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

	def open_keepass(self):
		subprocess.Popen(['keepassxc'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setpgrp)

	def update_properties(self):
		now = time.time()
		# try to fetch every 5s if no entries, 30s when cached entries exist
		if not self.last_check or (len(self._entries) == 0 and now - 5 > self.last_check) or ((now - 30 * 1 ) > self.last_check):
			self.last_check = now
			self.fetch_data()

	@property
	def labels(self) -> List[str]:
		self.update_properties()
		return self._labels

	@property
	def attributes(self) -> Dict[str, Dict]:
		self.update_properties()
		return self._attributes

	@property
	def passwords(self) -> Dict[str, dbus.ObjectPath]:
		self.update_properties()
		return self._entries


	def fetch_data(self):

		labels = []
		attributes = {}
		entries = {}

		try:
			passwords = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets/collection/passwords')
			#print(passwords.Introspect())
			iface = dbus.Interface(passwords, 'org.freedesktop.DBus.Properties')
			items = iface.GetAll('org.freedesktop.Secret.Collection')
			
			for item in items.get('Items'):
				password = self.bus.get_object(self.BUS_NAME, item)
				iface2 = dbus.Interface(password, 'org.freedesktop.DBus.Properties')
				items = iface2.GetAll('org.freedesktop.Secret.Item')
				label = str(items.get('Label'))
				labels.append(label)


				attr = items.get('Attributes')
				attributes[label] = attr

				entries[label] = item

		except dbus.exceptions.DBusException as e:
			# keepassxc not running	or database closed
			pass

		self._labels = labels
		self._attributes = attributes
		self._entries = entries

	def clear_cache(self):
		self._labels = []
		self._attributes = {}
		self._entries = {}

	def get_attribute(self, label: str, attribute_name: str) -> str:
		attribute_value = ""
		try:
			attributes = self.attributes[label]
			attribute_value = attributes[attribute_name]
		except KeyError:
			pass

		return attribute_value

	def get_url(self, label: str) -> str:
		return self.get_attribute(label, 'URL')

	def get_username(self, label: str) -> str:
		return self.get_attribute(label, 'UserName')

	def get_secret(self, label: str) -> str:
		session = self.session

		path = self.passwords[label]
		password = self.bus.get_object(self.BUS_NAME, path)
		iface = dbus.Interface(password, 'org.freedesktop.Secret.Item')

		result = iface.GetSecret(str(session))
		secret = ""

		#result[2] is a list of bytes
		if not self.crypto.active:
			secret = bytes(result[2]).decode('utf-8')
		else:
			secret = self.crypto.decrypt_message(result)

		return secret
