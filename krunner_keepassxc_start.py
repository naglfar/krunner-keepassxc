import argparse

from krunner_keepassxc.keepass import KeepassPasswords
from krunner_keepassxc.runner import Runner

def main():
	parser = argparse.ArgumentParser(prog="krunner-keepassxc")
	subparsers = parser.add_subparsers(dest="command")
	parser_runner = subparsers.add_parser('run', help='starts the krunner service, this is the default command')
	parser_cli = subparsers.add_parser('cli', help='a basic cli, mostly for testing purposes')
	parser_cli.add_argument("-l", "--labels", help="list the entries in your opened database", action="store_true", dest="list")
	parser_cli.add_argument("-p", "--password", help="get the password for one of your entries", dest="password")

	args = parser.parse_args()

	if args.command == "cli":

		kp = KeepassPasswords()
		if args.list:
			print(kp.labels)
		elif args.password:
			secret = kp.get_secret(args.password)
			print(secret or 'Nothing found')
		else:
			parser_cli.print_help()

	else:
		runner = Runner()
		runner.start()


if __name__ == '__main__':
	main()
