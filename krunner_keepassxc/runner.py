#!/bin/env python3
from multiprocessing.sharedctypes import Value
import time
import signal
import os
import configparser

from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from setproctitle import setproctitle, setthreadtitle
from xdg import xdg_config_home

from typing import List

from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE="org.kde.krunner1"

class Runner(dbus.service.Object):

	app_name = "krunner-keepassxc"

	# config vars
	config = {
		"trigger": "",
		"max_entries": 5,
		"icon": "object-unlocked",
	}
	config_numbers = [ 'max_entries' ]
	config_comments = {
		"trigger": "characters to trigger password lookup, can be empty (default)",
		"max_entries": "maximum number of entries to list (default: 5)",
		"icon": "the icon to use, you can find possible values in /usr/share/icons/<your theme>/ (default: object-unlock)",
	}

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

		self.check_config()

		self.kp = KeepassPasswords(mainloop)
		self.cp = Clipboard()
		self.last_match = 0

	def check_config(self):
		config = configparser.ConfigParser(allow_no_value=True)
		section = config[configparser.DEFAULTSECT]
		filename = f'{xdg_config_home()}{os.sep}{self.app_name}{os.sep}config'
		if not os.path.exists(filename):
			for k, v in self.config.items():
				section['# ' + self.config_comments[k]] = None
				section[k] = str(v)

			os.makedirs(os.path.dirname(filename), exist_ok=True)
			with open(filename, 'w') as file:
				config.write(file)

		else:
			config.read(filename)
			for k, v in section.items():
				if k in self.config:
					if k in self.config_numbers:
						try:
							v = int(v)
						except ValueError:
							v = self.config[k]
					self.config[k] = v

			update = False
			for k, v in self.config.items():
				if not k in section:
					section['# ' + self.config_comments[k]] = None
					section[k] = str(v)
					update = True
			if update:
				with open(filename, 'w') as file:
					config.write(file)

	def start(self):

		setproctitle('self.app_name')
		setthreadtitle('self.app_name')

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
				print(f' Quitting {self.app_name}')
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
		if len(query) > 2 and query.startswith(self.config['trigger']+' '):

			query = query[len(self.config['trigger']):].strip()

			if not self.cp.can_clip:
				self.cp.check_executables()

			if not self.cp.can_clip:
				matches = [
					('', "Neither xsel nor xclip installed", self.config['icon'], 100, 0.1, {})
				]

			elif len(self.kp.entries) == 0:
				if not self.kp.is_keepass_installed():
					matches = [
						('', "KeepassXC does not seem to be installed", self.config['icon'], 100, 0.1, {})
					]
				elif not self.kp.BUS_NAME:
					matches = [
						('', "DBUS bus name not found", self.config['icon'], 100, 0.1, { })
					]
				else:
					# no passwords found, show open keepass message
					matches = [
						('', "No passwords or database locked", self.config['icon'], 100, 0.1, { 'subtext': 'Open KeepassXC' })
					]
					self.empty_action = 'open-keepassxc'
			else:
				# find entries that contain the query
				# TODO: better search / fuzzy?
				entries = [e for e in self.kp.entries if query.lower() in e["label"].lower()]

				# sort entries starting with the query on top
				# [print(e["label"]) for e in entries]
				entries.sort(key=lambda entry: (not entry["label"].lower().startswith(query.lower()), entry["label"]))

				# max entries
				entries = entries[:self.config['max_entries']]

				matches = [
				#	data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
					(entry["path"], entry["label"], self.config['icon'], 100, (1 - (i * 0.1)), { 'subtext': self.kp.get_username(entry["path"]) }) for i, entry in enumerate(entries)
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

