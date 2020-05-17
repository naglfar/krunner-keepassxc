#!/bin/env python3

import argparse

from krunner_keepassxc.keepass import KeepassPasswords

def cli():
	parser = argparse.ArgumentParser()
	parser.add_argument("-l", "--labels", help="list the entries in your opened database", action="store_true", dest="list")
	parser.add_argument("-p", "--password", help="get the password for one of your entries", dest="password")
	args = parser.parse_args()
	
	kp = KeepassPasswords()
	if args.list:
		labels = kp.labels
		print(labels)
	elif args.password:
		secret = kp.getSecret(args.password)
		print(secret or 'Nothing found')
	else:
		#parser.print_help()
		print(kp.getSecret('test'))


if __name__ == '__main__':	
	cli()