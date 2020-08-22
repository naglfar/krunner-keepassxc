import argparse

from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.runner import Runner

# FIXME: just for poetry
def cli():
	import sys
	sys.argv.insert(1, 'cli')
	main()

def main():
	parser = argparse.ArgumentParser(prog="krunner-keepassxc", description="krunner plugin for querying KeepassXC, includes a small cli for querying manually.")
	subparsers = parser.add_subparsers(dest="command")
	subparsers.add_parser('run', help='starts the krunner service')
	parser.add_argument("-l", "--labels", help="list the entries in your opened database", action="store_true", dest="list")
	parser.add_argument("-u", "--user", help="get the username for one of your entries by label", dest="user", metavar=("label",))
	parser.add_argument("-p", "--password", help="get the password for one of your entries by label", dest="password", metavar=("label",))

	args = parser.parse_args()

	if args.command == "run":
		runner = Runner()
		runner.start()

	else:
		kp = KeepassPasswords()
		if args.list:
			print(kp.labels)
		elif args.user:
			user = kp.get_username(args.user)
			print(user or 'Nothing found')
		elif args.password:
			secret = kp.get_secret(args.password)
			print(secret or 'Nothing found')
		else:
			parser.print_help()


if __name__ == '__main__':
	main()
