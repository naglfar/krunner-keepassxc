#!/bin/env python3
from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE="org.kde.krunner1"


class Runner(dbus.service.Object):
	
	kp = None
	cp = None
	
	def __init__(self):
		
		DBusGMainLoop(set_as_default=True)
		
		sessionbus = dbus.SessionBus()
		sessionbus.request_name(BUS_NAME, dbus.bus.NAME_FLAG_REPLACE_EXISTING)
		bus_name = dbus.service.BusName(BUS_NAME, bus=sessionbus)
		dbus.service.Object.__init__(self, bus_name, OBJ_PATH)
		
		self.kp = KeepassPasswords()
		self.cp = Clipboard()

	def run(self):	
		loop = GLib.MainLoop()
		loop.run()

	@dbus.service.method(IFACE, out_signature='a(sss)')
	def Actions(self, msg):
		# FIXME: does not seem to get called at all
		return ['','','']

	@dbus.service.method(IFACE, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query):
		
		if len(query) > 2:
			# find entries that contain the query
			items = [i for i in self.kp.labels if query.lower() in i.lower()]
			# sort entries starting with the query on top
			items.sort(key=lambda item: (not item.startswith(query), item))
			# max 5 entries
			items = items[:5]
			#		data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
			return [(item,"Copy to clipboard: " + item,"object-unlocked",100,(1 - (i * 0.1)),{}) for i,item in enumerate(items)]
		
		return []
		

	@dbus.service.method(IFACE, in_signature='ss',)
	def Run(self, matchId, actionId):
		# matchId is data from Match
		if len(matchId) > 0:
			secret = self.kp.getSecret(matchId)
			if secret:
				try:
					self.cp.copy(secret)
				except NotImplementedError as e:
					print('neither xsel nor xclip seem to be installed', flush=True)
				except Exception as e:
					print(str(e), flush=True)
				
		return
