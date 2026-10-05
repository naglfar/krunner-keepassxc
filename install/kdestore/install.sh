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

# restart krunner
if command -v kquitapp6 >/dev/null 2>&1; then
	kquitapp6 krunner >/dev/null 2>&1 || pkill -f krunner
elif command -v kquitapp5 >/dev/null 2>&1; then
	kquitapp5 krunner >/dev/null 2>&1 || pkill -f krunner
else
	pkill -f krunner
fi

sleep 1

if command -v kstart6 >/dev/null 2>&1; then
	kstart6 krunner >/dev/null 2>&1
elif command -v kstart5 >/dev/null 2>&1; then
	kstart5 krunner >/dev/null 2>&1
else
	nohup krunner >/dev/null 2>&1 &
fi
