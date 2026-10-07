import argparse
import asyncio
import os
import sys
import time
import configparser
from typing import cast

from xdg import xdg_config_home

from .types import Config

from .configparser import CommentConfigParser
from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.runner import Runner


app_name = 'krunner-keepassxc'
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


def read_config():
	parser = configparser.ConfigParser(allow_no_value=True)
	section = parser[configparser.DEFAULTSECT]
	filename = f'{xdg_config_home()}{os.sep}{app_name}{os.sep}config'
	if not os.path.exists(filename):
		for k, v in config.items():
			section['# ' + config_comments[k]] = None	#type: ignore
			section[k] = str(v)

		os.makedirs(os.path.dirname(filename), exist_ok=True)
		with open(filename, 'w') as file:
			parser.write(file)

	else:
		parser.read(filename)
		for k, v in section.items():
			if k in config:
				if k in config_numbers:
					try:
						v = int(cast(int, v))
					except ValueError:
						v = config[k]	# type: ignore
				config[k] = v	# type: ignore

		update = False
		for k, v in config.items():
			if not k in section:
				section['# ' + config_comments[k]] = None	#type: ignore
				section[k] = str(v)
				update = True
		if update:
			with open(filename, 'w') as file:
				parser.write(file)

	if len(config['trigger']) > 0: config['trigger'] += ' '


async def main():

	read_config()

	parser = argparse.ArgumentParser(prog="krunner-keepassxc", description="krunner plugin for querying KeepassXC, includes a small cli for querying manually.")
	subparsers = parser.add_subparsers(dest="command")
	subparsers.add_parser('run', help='starts the krunner service')
	parser.add_argument("-l", "--list", help="list the entries in your opened databases", action="store_true", dest="list")
	parser.add_argument("-u", "--user", help="get the username for entries looked up by label", dest="user", metavar=("label",))
	parser.add_argument("-t", "--totp", help="get the TOTP for entries looked up by label", dest="totp", metavar=("label",))
	parser.add_argument("-p", "--password", help="get the password for entries looked up by label", dest="password", metavar=("label",))
	parser.add_argument("-s", "--search", help="Search for entries", dest="search", metavar=("query",))

	args = parser.parse_args()

	if args.command == "run":

		# on some configurations the services starts before environment variables have been set,
		# i.e. the user has logged in, even though systemd is supposed to manage this correctly
		# as a dirty hack we sleep 10 seconds and exit, so that the service gets restarted
		if not 'DISPLAY' in os.environ:
			time.sleep(10)
			sys.exit('environment missing, exiting')

		runner = Runner(config)
		await runner.run()

	else:
		kp = await KeepassPasswords(config)

		if args.list:
			print("\n".join([f'{e["label"]} ({e["attributes"]["Path"]})' for e in await kp.get_entries()]))

		elif args.user:
			entries = list(filter(lambda e: e["label"] == args.user, await kp.get_entries()))
			if len(entries) > 0:
				for entry in entries:
					user = await kp.get_username(entry["path"])
					print(f'{entry["label"]} ({entry["attributes"]["Path"]}): {user}')
			else:
				print('Nothing found')

		elif args.totp:
			entries = list(filter(lambda e: e["label"] == args.totp, await kp.get_entries()))
			if len(entries) > 0:
				for entry in entries:
					totp = await kp.get_totp(entry["path"])
					if totp:
						print(f'{entry["label"]} ({entry["attributes"]["Path"]}): {totp}')
			else:
				print('Nothing found')

		elif args.password:
			entries = list(filter(lambda e: e["label"] == args.password, await kp.get_entries()))
			if len(entries) > 0:
				for entry in entries:
					secret = await kp.get_secret(entry["path"])
					print(f'{entry["label"]} ({entry["attributes"]["Path"]}): {secret}')
			else:
				print('Nothing found')

		elif args.search:
			query = args.search

			entries = [e for e in await kp.get_entries() if any([
				all(x in e["attributes"]["Path"].lower() for x in query.lower().split(' ')),
				all(x in e["attributes"]["URL"].lower() for x in query.lower().split(' ')),
				all(x in e["attributes"]["UserName"].lower() for x in query.lower().split(' ')),
			])]

			entries.sort(key=lambda entry: (
					not entry["label"].lower().startswith(query.lower()),
					not query.lower() in entry["label"].lower(),
					entry["label"]
				)
			)

			for entry in entries:
				print(f'{entry["label"]} ({entry["attributes"]["Path"]})')

		else:
			parser.print_help()

def runner():
	import sys
	sys.argv.insert(1, 'run')
	asyncio.run(main())

def cli():
	asyncio.run(main())

if __name__ == '__main__':
	cli()
