import argparse
import asyncio

from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.runner import Runner

from .config import config, read_config
from .search import search


async def main() -> None:

	read_config()

	parser = argparse.ArgumentParser(prog="krunner-keepassxc", description="krunner plugin for querying KeepassXC, includes a small cli for querying manually.")
	subparsers = parser.add_subparsers(dest="command")
	run_parser = subparsers.add_parser('run', help='starts the krunner service')
	run_parser.add_argument("--idle-timeout", type=int, dest="idle_timeout", metavar="SECONDS",
		help="overrides idle_timeout from the config file, 0 keeps the service running (useful for development)")
	parser.add_argument("-l", "--list", help="list the entries in your opened databases", action="store_true", dest="list")
	parser.add_argument("-u", "--user", help="get the username for entries looked up by label", dest="user", metavar=("label",))
	parser.add_argument("-t", "--totp", help="get the TOTP for entries looked up by label", dest="totp", metavar=("label",))
	parser.add_argument("-p", "--password", help="get the password for entries looked up by label", dest="password", metavar=("label",))
	parser.add_argument("-s", "--search", help="Search for entries", dest="search", metavar=("query",))

	args = parser.parse_args()

	if args.command == "run":

		# the service is started on demand by the D-Bus daemon (see
		# install/de.naglfar.krunner-keepassxc.service), so it inherits the
		# session's activation environment and no startup workarounds are needed
		if args.idle_timeout is not None:
			config['idle_timeout'] = args.idle_timeout
		runner = Runner(config)
		try:
			await runner.run()
		except asyncio.exceptions.CancelledError:
			print("\nStopping runner.")

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
			for entry in search(await kp.get_entries(), args.search):
				print(f'{entry["label"]} ({entry["attributes"]["Path"]})')

		else:
			parser.print_help()

def runner() -> None:
	import sys
	sys.argv.insert(1, 'run')
	sys.argv.insert(2, '--idle-timeout')
	sys.argv.insert(3, '0')
	asyncio.run(main())

def cli() -> None:
	asyncio.run(main())

if __name__ == '__main__':
	cli()
