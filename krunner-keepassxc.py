#!/bin/env python3
from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from Clipboard import Clipboard
from KeepassPasswords import KeepassPasswords

objpath="/krunner"
iface="org.kde.krunner1"


class Runner(dbus.service.Object):
	
	kp = None
	cp = None
	
	def __init__(self):
		dbus.service.Object.__init__(self, dbus.service.BusName("de.naglfar.krunner-keepassxc", dbus.SessionBus()), objpath)
		self.kp = KeepassPasswords()
		self.cp = Clipboard()

	@dbus.service.method(iface, out_signature='a(sss)')
	def Actions(self, msg):
		# FIXME: does not seem to get called at all
		return ['','','']

	@dbus.service.method(iface, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query):
		
		if len(query) > 2:
			items = [i for i in self.kp.labels if query.lower() in i.lower()]
			items.sort(key=lambda item: (not item.startswith(query), item))
			return [(item,"Copy to clipboard: " + item,"object-unlocked",100,(1 - (i * 0.01)),{}) for i,item in enumerate(items)]
		
		return []
		

	@dbus.service.method(iface, in_signature='ss',)
	def Run(self, matchId, actionId):

		if len(matchId) > 0:
			secret = self.kp.getSecret(matchId)
			if secret:
				secret = secret.replace('"','\\"')
				secret = secret.replace("'","\\'")
				self.cp.copy(secret)
				
		return


if __name__ == '__main__':
	
	DBusGMainLoop(set_as_default=True)
	    
	runner = Runner()
	loop = GLib.MainLoop()

	loop.run()
