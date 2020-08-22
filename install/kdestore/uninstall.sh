#!/bin/bash
pwd=$(pwd)
kservices_path=$(kf5-config --path services | awk -F: '{print $1}')

if [ -d "/run/systemd/system" ]
then
	# systemd
	unitpath=$XDG_DATA_HOME
	if [[ -z "${unitpath}" ]]; then
		unitpath=$HOME/.local/share/systemd/user
	fi
	systemctl --user stop krunner-keepassxc && systemctl --user disable krunner-keepassxc
	rm -f "${unitpath}/krunner-keepassxc.service"
else
	# autostart
	pkill -f "krunner-keepassxc\.pyz"
	autostartpath="~/.local/share/autostart"
	rm -f "${autostartpath}/krunner-keepassxc_autostart.desktop"
fi

rm "${kservices_path}/krunner-keepassxc.desktop"
rm "$HOME/.local/bin/krunner-keepassxc.pyz"

kquitapp5 krunner
kstart5 --windowclass krunner krunner
