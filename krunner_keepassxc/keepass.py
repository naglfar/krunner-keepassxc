#!/bin/env python3

import argparse
import dbus
import os
import time

from typing import Dict, List, Optional

from .dhcrypto import dhcrypto

class KeepassPasswords:

	#BUS_NAME: str = 'org.keepassxc.KeePassXC.MainWindow'
	BUS_NAME: str = 'org.freedesktop.secrets'

	bus: dbus._dbus.SessionBus
	_session: Optional[str]
	lastCheck: Optional[float]
	_labels: List[str]
	_passwords: Dict[str, dbus.ObjectPath]

	crypto: dhcrypto

	def __init__(self):
		self.bus = dbus.SessionBus()
		self._session = None
		self.lastCheck = None

		self._labels = []
		self._passwords = {}

		self.crypto = dhcrypto()

	@property
	def session(self) -> Optional[str]:
		if not self._session:
			secrets = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets')
			iface = dbus.Interface(secrets, 'org.freedesktop.Secret.Service')

			if not self.crypto.active:
				_output, sessionPath = iface.OpenSession('plain', '')
			else:
				server_pubkey, sessionPath = iface.OpenSession('dh-ietf1024-sha256-aes128-cbc-pkcs7', dbus.ByteArray(self.crypto.pubkey_as_bytes()))
				self.crypto.set_server_public_key(server_pubkey)

			self._session = sessionPath

		return self._session


	def updateProperties(self):
		now = time.time()
		if not self.lastCheck or (now - 60 * 5 ) > self.lastCheck:
			self.lastCheck = now
			self.fetchData()

	@property
	def labels(self) -> List[str]:
		self.updateProperties()
		return self._labels

	@property
	def passwords(self) -> Dict[str, dbus.ObjectPath]:
		self.updateProperties()
		return self._passwords


	def fetchData(self):

		passwords = self.bus.get_object(self.BUS_NAME, '/org/freedesktop/secrets/collection/passwords')

		#print(passwords.Introspect())

		iface = dbus.Interface(passwords, 'org.freedesktop.DBus.Properties')

		items = iface.GetAll('org.freedesktop.Secret.Collection')

		labels = []
		passwords = {}
		for item in items.get('Items'):
			password = self.bus.get_object(self.BUS_NAME, item)
			#print(password.Introspect())
			iface2 = dbus.Interface(password, 'org.freedesktop.DBus.Properties')
			items = iface2.GetAll('org.freedesktop.Secret.Item')
			label = items.get('Label')
			labels.append(str(label))
			passwords[label] = item

		self._labels = labels
		self._passwords = passwords

	def getSecret(self, label: str) -> str:
		s = self.session

		path = self.passwords[label]
		password = self.bus.get_object(self.BUS_NAME, path)
		#print(password.Introspect())
		iface = dbus.Interface(password, 'org.freedesktop.Secret.Item')

		result = iface.GetSecret(str(s))
		secret = ""

		#result[2] is a list of bytes
		if not self.crypto.active:
			secret = bytes(result[2]).decode('utf-8')
		else:
			secret = self.crypto.decryptMessage(result)

		return secret
