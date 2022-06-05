import argparse

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
	parser.add_argument("-l", "--labels", help="list the entries in your opened database", action="store_true", dest="list")
	parser.add_argument("-u", "--user", help="get the username for one of your entries by label", dest="user", metavar=("label",))
	parser.add_argument("-t", "--totp", help="get the TOTP for one of your entries by label", dest="totp", metavar=("label",))
	parser.add_argument("-p", "--password", help="get the password for one of your entries by label", dest="password", metavar=("label",))

	args = parser.parse_args()

	if args.command == "run":
		runner = Runner()
		runner.start()

	else:
		kp = KeepassPasswords()
		if args.list:
			print([e['label'] for e in kp.entries])
		elif args.user:
			entries = list(filter(lambda e: e["label"] == args.user, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					user = kp.get_username(entry["path"])
					print(user)
			else:
				print('Nothing found')
		elif args.totp:
			entries = list(filter(lambda e: e["label"] == args.totp, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					totp = kp.get_totp(entry["path"])
					print(totp)
			else:
				print('Nothing found')
		elif args.password:
			entries = list(filter(lambda e: e["label"] == args.password, kp.entries))
			if len(entries) > 0:
				for entry in entries:
					kp.get_secret(entry["path"], lambda secret: print(secret))
			else:
				print('Nothing found')
		else:
			parser.print_help()


if __name__ == '__main__':
	main()
