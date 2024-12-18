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

from typing import List, cast
from .types import Config, Entry

from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE="org.kde.krunner1"

class Runner(dbus.service.Object):

	app_name = "krunner-keepassxc"

	# config vars
	config: Config = {
		"trigger": "",
		"max_entries": 5,
		"icon": "object-unlocked",
		"totp_as_extra_entry": "True"
	}
	config_numbers = [ 'max_entries' ]
	config_comments = {
		"trigger": "characters to trigger password lookup, can be empty (default)",
		"max_entries": "maximum number of entries to list (default: 5)",
		"icon": "the icon to use, you can find possible values in /usr/share/icons/<your theme>/ (default: object-unlock)",
		"totp_as_extra_entry": "if you have TOTP entries they will show up as extra list entries instead of another action icon (true / false)"
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

		self.kp = KeepassPasswords(mainloop, self.config)
		self.cp = Clipboard()
		self.last_match = 0

	def check_config(self):
		config = configparser.ConfigParser(allow_no_value=True)
		section = config[configparser.DEFAULTSECT]
		filename = f'{xdg_config_home()}{os.sep}{self.app_name}{os.sep}config'
		if not os.path.exists(filename):
			for k, v in self.config.items():
				section['# ' + self.config_comments[k]] = None	#type: ignore
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
							v = int(cast(int, v))
						except ValueError:
							v = self.config[k]	# type: ignore
					self.config[k] = v	# type: ignore

			update = False
			for k, v in self.config.items():
				if not k in section:
					section['# ' + self.config_comments[k]] = None	#type: ignore
					section[k] = str(v)
					update = True
			if update:
				with open(filename, 'w') as file:
					config.write(file)

		if len(self.config['trigger']) > 0: self.config['trigger'] += ' '

	def start(self):

		setproctitle(self.app_name)
		setthreadtitle(self.app_name)

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
		# populate entries to check for otp
		self.kp.update_properties()
		actions = [
			('user', 'copy username', 'username-copy'),
		]
		if self.kp.otp and "totp_as_extra_entry" in self.config and self.config["totp_as_extra_entry"].lower() == 'false':
			actions.append(
				('totp', 'copy TOTP', 'accept_time_event'),
			)
		return actions

	@dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query: str) -> List:

		matches:List = []
		if len(query) > 2 and query.startswith(self.config['trigger']):

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
				# find entries that contain the query, Path attribute contains keepass group name
				# TODO: maybe search through additional attributes aswell?
				entries = [e for e in self.kp.entries if any([
					all(x in e["attributes"]["Path"].lower() for x in query.lower().split(' ')),
					all(x in e["attributes"]["URL"].lower() for x in query.lower().split(' ')),
					all(x in e["attributes"]["UserName"].lower() for x in query.lower().split(' ')),
				])]

				# sort entries where the label starts with the query to the top
				# sort entries containing the query in the label over path next
				# everything else comes after
				# [print(e["label"]) for e in entries]
				entries.sort(key=lambda entry: (
						not entry["label"].lower().startswith(query.lower()),
						not query.lower() in entry["label"].lower(),
						entry["label"]
					)
				)

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

			# forcing action for specific entries (i.e. TOTP)
			split_match = matchId.split(':')
			if len(split_match) > 1:
				matchId = split_match[0]
				actionId = split_match[1]

			if actionId == 'user':
				user = self.kp.get_username(matchId)
				self.copy_to_clipboard(user)
			elif actionId == 'totp':
				totp = self.kp.get_totp(matchId)
				if totp:
					self.copy_to_clipboard(totp)
			else:
				secret = self.kp.get_secret(matchId, lambda secret: self.copy_to_clipboard(secret))
				# self.copy_to_clipboard(secret)

			# clear all cached data on action
			self.kp.clear_cache()
			# clear last_match to skip needless check_cache
			self.last_match = 0

		self.empty_action = ""

