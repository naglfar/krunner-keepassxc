#!/bin/env python3
import time
import signal

from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from typing import List

from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE="org.kde.krunner1"


class Runner(dbus.service.Object):

	kp: KeepassPasswords
	cp: Clipboard
	last_match: float

	def __init__(self):

		DBusGMainLoop(set_as_default=True)

		sessionbus = dbus.SessionBus()
		sessionbus.request_name(BUS_NAME, dbus.bus.NAME_FLAG_REPLACE_EXISTING)
		bus_name = dbus.service.BusName(BUS_NAME, bus=sessionbus)
		dbus.service.Object.__init__(self, bus_name, OBJ_PATH)

		self.kp = KeepassPasswords()
		self.cp = Clipboard()
		self.last_match = None

	def start(self):

		loop = GLib.MainLoop()

		# clear saved data 15 seconds after last krunner match call
		def check_cache():
			if self.last_match:
				now = time.time()
				if now - 15 > self.last_match:
					self.last_match = None
					self.kp.clear_cache()

			# return true to keep getting called, false to stop
			return True

		GLib.timeout_add(1000, check_cache)

		# handle sigint
		def sigint_handler(sig, frame):
			if sig == signal.SIGINT:
				print(' Quitting krunner-keepassxc')
				loop.quit()
			else:
				raise ValueError("Undefined handler for '{}'".format(sig))

		signal.signal(signal.SIGINT, sigint_handler)

		# start the main loop
		loop.run()


	def copy_to_clipboard(self, string: str):
		if string:
			try:
				self.cp.copy(string)
			except NotImplementedError as e:
				print('neither xsel nor xclip seem to be installed', flush=True)
			except Exception as e:
				print(str(e), flush=True)

	@dbus.service.method(IFACE, out_signature='a(sss)')
	def Actions(self):
		# define our secondary action(s)
		if len(self.kp.labels) == 0:
			return []
		else:
			return [
				('user', 'copy username', 'username-copy'),
			]

	@dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query: str) -> List:
		
		matches = []

		if len(query) > 2:

			if len(self.kp.labels) == 0:
				# no passwords found, show open keepass message
				matches = [
					('', "No passwords or database locked", "object-unlocked", 100, 0.1, { 'subtext': 'Open KeepassXC' })
				]

			else:
				# find entries that contain the query
				items = [i for i in self.kp.labels if query.lower() in i.lower()]
				# sort entries starting with the query on top
				items.sort(key=lambda item: (not item.startswith(query), item))
				# max 5 entries
				items = items[:5]

				matches = [
				#	data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
					(item, "Copy to clipboard: " + item, "object-unlocked", 100, (1 - (i * 0.1)), { 'subtext': self.kp.get_username(item) }) for i, item in enumerate(items)
				]

				self.last_match = time.time()

		return matches


	@dbus.service.method(IFACE, in_signature='ss',)
	def Run(self, matchId: str, actionId: str):
		# matchId is data from Match, actionId is secondary action or empty for primary
		
		if len(matchId) == 0:
			# empty matchId means keepassxc isn't running or database is locked
			self.kp.open_keepass()

		else:
			if actionId == 'user':
				user = self.kp.get_username(matchId)
				self.copy_to_clipboard(user)
			else:
				secret = self.kp.get_secret(matchId)
				self.copy_to_clipboard(secret)
			
			# clear all cached data on action
			self.kp.clear_cache()
			# clear last_match to skip needless check_cache
			self.last_match = None

				
