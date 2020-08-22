#!/bin/bash
pwd=$(pwd)
pyz="$pwd/krunner_keepassxc.pyz"

kservices_path=$(kf5-config --path services | awk -F: '{print $1}')
if [[ -z "${kservices_path}" ]]; then
	kservices_path="$HOME/.local/share/kservices5/"
fi
if [ ! -d "${kservices_path}" ]; then
	mkdir -p "${kservices_path}"
fi
cp krunner-keepassxc.desktop "${kservices_path}"

if [ -d "/run/systemd/system" ]
then
	# systemd
	unitpath=$XDG_DATA_HOME
	if [[ -z "${unitpath}" ]]; then
		unitpath="$HOME/.local/share/systemd/user"
	fi
	if [ ! -d "${unitpath}" ]; then
		mkdir -p "${unitpath}"
	fi
	sed "s|##execstart##|${pyz}|" "krunner-keepassxc.service" > "${unitpath}/krunner-keepassxc.service"
	
	systemctl --user enable krunner-keepassxc && systemctl --user start krunner-keepassxc

else
	# autostart
	autostartpath="~/.local/share/autostart"
	if [ ! -d "${autostartpath}" ]; then
		mkdir -p "${autostartpath}"
	fi
	sed "s|##exec##|${pyz}|" "krunner-keepassxc_autostart.desktop" > "${autostartpath}/krunner-keepassxc_autostart.desktop"
	eval "${pyz}" &>/dev/null & disown;
fi

kquitapp5 krunner
kstart5 --windowclass krunner krunner
