#!/bin/env python3

import argparse
import dbus
import os
import time
from .dhcrypto import dhcrypto

class KeepassPasswords:

	bus = None
	_session = None
	lastCheck = None
	_labels = []
	_passwords = {}
	
	crypto = None
	
	def __init__(self):
		self.bus = dbus.SessionBus()
		
		self.crypto = dhcrypto()
			
	@property
	def session(self):
		if not self._session:
			secrets = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', '/org/freedesktop/secrets')
			iface = dbus.Interface(secrets, 'org.freedesktop.Secret.Service')

			if not self.crypto.active:
				output, sessionPath = iface.OpenSession('plain', '')
			else:
				output, sessionPath = iface.OpenSession('dh-ietf1024-sha256-aes128-cbc-pkcs7', self.crypto.pubkey_as_list())
				self.crypto.set_server_public_key(output)
			
			self._session = sessionPath
		
		return self._session
			
	
	def updateProperties(self):
		now = time.time()
		if not self.lastCheck or (now - 60 * 5 ) > self.lastCheck:
			self.lastCheck = now
			self.fetchData()
	
	@property
	def labels(self):
		self.updateProperties()
		return self._labels
		
	@property
	def passwords(self):
		self.updateProperties()		
		return self._passwords
		

	def fetchData(self):

		passwords = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', '/org/freedesktop/secrets/collection/passwords')

		#print(passwords.Introspect())

		iface = dbus.Interface(passwords, 'org.freedesktop.DBus.Properties')

		items = iface.GetAll('org.freedesktop.Secret.Collection')

		labels = []
		passwords = {}
		for item in items.get('Items'):
			password = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', item)
			#print(password.Introspect())
			iface2 = dbus.Interface(password, 'org.freedesktop.DBus.Properties')
			items = iface2.GetAll('org.freedesktop.Secret.Item')
			label = items.get('Label')
			labels.append(str(label))
			passwords[label] = item
			
		self._labels = labels
		self._passwords = passwords

	def getSecret(self, label):
		s = self.session

		path = self.passwords[label]
		password = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', path)
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