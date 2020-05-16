#!/bin/env python3

import argparse
import dbus
import time

class KeepassPasswords:
	
	bus = None
	_session = None
	lastCheck = None
	_labels = []
	_passwords = {}
	
	def __init__(self):
		self.bus = dbus.SessionBus()

			
	@property
	def session(self):
		if not self._session:
			secrets = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', '/org/freedesktop/secrets')
			iface = dbus.Interface(secrets, 'org.freedesktop.Secret.Service')
			session = iface.OpenSession('plain', '')
			
			self._session = session[1]
		
		return self._session
			
			
	@property
	def labels(self):
		
		now = time.time()
		if not self.lastCheck or (now - 60 * 5 ) > self.lastCheck:
			self.lastCheck = now
			self.fetchData()
		
		return self._labels
		
	@property
	def passwords(self):
		
		now = time.time()
		if not self.lastCheck or (now - 60 * 5 ) > self.lastCheck:
			self.lastCheck = now
			self.fetchData()
		
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

		secret = ""
		try:
			path = self.passwords[label]
			password = self.bus.get_object('org.keepassxc.KeePassXC.MainWindow', path)
			#print(password.Introspect())
			iface = dbus.Interface(password, 'org.freedesktop.Secret.Item')
			
			result = iface.GetSecret(str(s))

			secret = ""
			for byteValue in result[2]:
				secret += chr(byteValue)
		except:
			pass
		
		return secret
		
		
			


if __name__ == '__main__':
	
	parser = argparse.ArgumentParser()
	parser.add_argument("-l", "--labels", help="list the entries in your opened database", action="store_true", dest="list")
	parser.add_argument("-p", "--password", help="get the password for one of your entries", dest="password")
	args = parser.parse_args()
	
	kp = KeepassPasswords()
	if args.list:
		labels = kp.labels
		print(labels)
	elif args.password:
		secret = kp.getSecret(args.password)
		print(secret or 'Nothing found')
	else:
		parser.print_help()