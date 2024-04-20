#!/bin/bash
pwd=$(pwd)
dbusplugins_path="$HOME/.local/share/krunner/dbusplugins"

if [ -d "/run/systemd/system" ]
then
	# systemd
	unitpath=$XDG_DATA_HOME	# should be ~/.local/share
	if [[ -z "${unitpath}" ]]; then
		unitpath="$HOME/.local/share/systemd/user"
	else
		unitpath="$unitpath/systemd/user"
	fi
	systemctl --user stop krunner-keepassxc && systemctl --user disable krunner-keepassxc
	rm -f "${unitpath}/krunner-keepassxc.service"
else
	# autostart
	pkill -f "krunner-keepassxc\.pyz"
	autostartpath="~/.local/share/autostart"
	rm -f "${autostartpath}/krunner-keepassxc_autostart.desktop"
fi


rm "${dbusplugins_path}/krunner-keepassxc.desktop"
rm "$HOME/.local/bin/krunner-keepassxc.pyz"

kquitapp krunner
kstart krunner
