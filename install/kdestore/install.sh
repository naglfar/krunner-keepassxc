#!/bin/bash
pwd=$(pwd)

bin="$HOME/.local/bin/"
if [ ! -d "${bin}" ]; then
	mkdir -p "${bin}"
fi
cp "$pwd/krunner-keepassxc.pyz" "$bin"
pyz="$bin/krunner-keepassxc.pyz run"

dbusplugins_path="$HOME/.local/share/krunner/dbusplugins/"
if [ ! -d "${dbusplugins_path}" ]; then
	mkdir -p "${dbusplugins_path}"
fi
cp krunner-keepassxc.desktop "${dbusplugins_path}"

if [ -d "/run/systemd/system" ]
then
	# systemd
	unitpath=$XDG_DATA_HOME	# should be ~/.local/share
	if [[ -z "${unitpath}" ]]; then
		unitpath="$HOME/.local/share/systemd/user"
	else
		unitpath="$unitpath/systemd/user"
	fi
	if [ ! -d "${unitpath}" ]; then
		mkdir -p "${unitpath}"
	fi
	cp "krunner-keepassxc.service" "${unitpath}/krunner-keepassxc.service"

	systemctl --user enable krunner-keepassxc && systemctl --user restart krunner-keepassxc

else
	# autostart
	autostartpath="~/.local/share/autostart"
	if [ ! -d "${autostartpath}" ]; then
		mkdir -p "${autostartpath}"
	fi
	sed "s|##exec##|${pyz}|" "krunner-keepassxc_autostart.desktop" > "${autostartpath}/krunner-keepassxc_autostart.desktop"
	pkill -f "krunner-keepassxc\.pyz"
	eval "${pyz}" &>/dev/null & disown;
fi

kquitapp krunner
kstart krunner
