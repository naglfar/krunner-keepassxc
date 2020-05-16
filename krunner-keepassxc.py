#!/bin/env python3
import subprocess
from gi.repository import GLib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop


objpath="/krunner"
iface="org.kde.krunner1"

class Runner(dbus.service.Object):
	
	def __init__(self):
		dbus.service.Object.__init__(self, dbus.service.BusName("de.naglfar.krunner-keepassxc", dbus.SessionBus()), objpath)

	@dbus.service.method(iface, out_signature='a(sss)')
	def Actions(self, msg):
		# FIXME: does not seem to get called at all
		return ['','','']

	@dbus.service.method(iface, in_signature='s', out_signature='a(sssida{sv})')
	def Match(self, query):
			
		#		data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
		return [(query,"Copy to clipboard","object-unlocked",100,0.9,{})]

	@dbus.service.method(iface, in_signature='ss',)
	def Run(self, matchId, actionId):

		result = subprocess.run("secret-tool lookup Title " + matchId, shell=True, stdout=subprocess.PIPE)
		for line in result.stdout.decode('utf-8').split('\n'):
			if line:
				#print(line)
				line = line.replace('"','\\"')
				line = line.replace("'","\\'")
				subprocess.run('printf "'+line+'" | xsel -b', shell=True, stdout=subprocess.PIPE)
				
		return


if __name__ == '__main__':
	
	DBusGMainLoop(set_as_default=True)
	    
	runner = Runner()
	loop = GLib.MainLoop()

	loop.run()
