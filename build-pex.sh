#!/bin/sh
pex . --disable-cache  --inherit-path -r pex_requirements.txt -e krunner_keepassxc -o dist/krunner_keepassxc.pex
