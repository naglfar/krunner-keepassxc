#!/bin/sh
shiv \
	-p "/usr/bin/env python3" \
	-e krunner_keepassxc.__main__:main \
	--output-file dist/krunner_keepassxc.pyz \
	.
