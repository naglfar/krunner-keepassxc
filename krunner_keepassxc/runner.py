#!/bin/env python3
import time
import signal

from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from setproctitle import setproctitle, setthreadtitle

from typing import List

from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE="org.kde.krunner1"

class Runner(dbus.service.Object):

	kp: KeepassPasswords
	cp: Clipboard
	empty_action: str = ""
	last_match: float

	def __init__(self):

		mainloop = DBusGMainLoop(set_as_default=True)

		sessionbus = dbus.SessionBus()
		sessionbus.request_name(BUS_NAME, dbus.bus.NAME_FLAG_REPLACE_EXISTING)
		bus_name = dbus.service.BusName(BUS_NAME, bus=sessionbus)
		dbus.service.Object.__init__(self, bus_name, OBJ_PATH)

		self.kp = KeepassPasswords(mainloop)
		self.cp = Clipboard()
		self.last_match = 0

	def start(self):

		setproctitle('krunner-keepassxc')
		setthreadtitle('krunner-keepassxc')

		loop = GLib.MainLoop()

		# clear saved data 15 seconds after last krunner match call
		def check_cache():
			if self.last_match:
				now = time.time()
				if now - 15 > self.last_match:
					self.last_match = 0
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
		if len(self.kp.entries) == 0:
			return []
		else:
			return [
				('user', 'copy username', 'username-copy'),
			]

	@dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query: str) -> List:

		matches:List = []
		if len(query) > 2:

			if not self.cp.can_clip:
				self.cp.check_executables()

			if not self.cp.can_clip:
				matches = [
					('', "Neither xsel nor xclip installed", "object-unlocked", 100, 0.1, {})
				]

			elif len(self.kp.entries) == 0:
				if not self.kp.is_keepass_installed():
					matches = [
						('', "KeepassXC does not seem to be installed", "object-unlocked", 100, 0.1, {})
					]
				elif not self.kp.BUS_NAME:
					matches = [
						('', "DBUS bus name not found", "object-unlocked", 100, 0.1, { })
					]
				else:
					# no passwords found, show open keepass message
					matches = [
						('', "No passwords or database locked", "object-unlocked", 100, 0.1, { 'subtext': 'Open KeepassXC' })
					]
					self.empty_action = 'open-keepassxc'
			else:
				# find entries that contain the query
				entries = [e for e in self.kp.entries if query.lower() in e["label"].lower()]
				# sort entries starting with the query on top
				# [print(e["label"]) for e in entries]
				entries.sort(key=lambda entry: (not entry["label"].lower().startswith(query.lower()), entry["label"]))
				# max 5 entries
				entries = entries[:5]

				matches = [
				#	data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
					(entry["path"], entry["label"], "object-unlocked", 100, (1 - (i * 0.1)), { 'subtext': self.kp.get_username(entry["path"]) }) for i, entry in enumerate(entries)
				]

				self.last_match = time.time()

		return matches


	@dbus.service.method(IFACE, in_signature='ss',)
	def Run(self, matchId: str, actionId: str):
		# matchId is data from Match, actionId is secondary action or empty for primary

		if len(matchId) == 0:
			# empty matchId means error of some kind
			if self.empty_action == 'open-keepassxc':
				self.kp.open_keepass()
		else:
			if actionId == 'user':
				user = self.kp.get_username(matchId)
				self.copy_to_clipboard(user)
			else:
				secret = self.kp.get_secret(matchId, lambda secret: self.copy_to_clipboard(secret))
				# self.copy_to_clipboard(secret)

			# clear all cached data on action
			self.kp.clear_cache()
			# clear last_match to skip needless check_cache
			self.last_match = 0

		self.empty_action = ""

