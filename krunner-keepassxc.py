#!/bin/env python3
import subprocess
from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from KeepassPasswords import KeepassPasswords

objpath="/krunner"
iface="org.kde.krunner1"


class Runner(dbus.service.Object):
	
	kp = None
	
	def __init__(self):
		dbus.service.Object.__init__(self, dbus.service.BusName("de.naglfar.krunner-keepassxc", dbus.SessionBus()), objpath)
		self.kp = KeepassPasswords()

	@dbus.service.method(iface, out_signature='a(sss)')
	def Actions(self, msg):
		# FIXME: does not seem to get called at all
		return ['','','']

	@dbus.service.method(iface, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query):
		
		if len(query) > 2:
			items = [i for i in self.kp.labels if query.lower() in i.lower()]
			if len(items) > 0:
				# if multiple items found, see if we can get a direct hit, else return the first one
				if len(items) > 1:
					directHit = [i for i in items if query.lower() == i.lower()]
					if len(directHit) > 0:
						items = directHit

				item = items[0]
					
				#		data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
				return [(item,"Copy to clipboard: " + item,"object-unlocked",100,1,{})]
		
		return []
		

	@dbus.service.method(iface, in_signature='ss',)
	def Run(self, matchId, actionId):

		if len(matchId) > 0:
			secret = self.kp.getSecret(matchId)
			if secret:
				secret = secret.replace('"','\\"')
				secret = secret.replace("'","\\'")
				subprocess.run('printf "'+secret+'" | xsel -b', shell=True, stdout=subprocess.PIPE)
				
		return


if __name__ == '__main__':
	
	DBusGMainLoop(set_as_default=True)
	    
	runner = Runner()
	loop = GLib.MainLoop()

	loop.run()
