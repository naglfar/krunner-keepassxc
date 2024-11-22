import argparse
import os
import sys
import time

from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.runner import Runner

# FIXME: just for poetry
def runner():
	import sys
	sys.argv.insert(1, 'run')
	main()

def main():

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

		runner = Runner()
		runner.start()

	else:
		kp = KeepassPasswords()

		if args.list:
			print("\n".join([e["attributes"]["Path"] for e in kp.entries]))

		elif args.user:
			entries = list(filter(lambda e: e["label"] == args.user, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					user = kp.get_username(entry["path"])
					print(f'{entry["attributes"]["Path"]}: {user}')
			else:
				print('Nothing found')

		elif args.totp:
			entries = list(filter(lambda e: e["label"] == args.totp, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					totp = kp.get_totp(entry["path"])
					if totp:
						print(f'{entry['attributes']['Path']}: {totp}')
			else:
				print('Nothing found')

		elif args.password:
			entries = list(filter(lambda e: e["label"] == args.password, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					kp.get_secret(entry["path"], lambda secret: print(f'{entry['attributes']['Path']}: {secret}'))
			else:
				print('Nothing found')

		elif args.search:
			query = args.search

			entries = [e for e in kp.entries if any([
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
				print(f'{entry["attributes"]["Path"]}')
			
		else:
			parser.print_help()


if __name__ == '__main__':
	main()
