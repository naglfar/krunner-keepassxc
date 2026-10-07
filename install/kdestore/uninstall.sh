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
	# old version
	pkill -f "krunner-keepassxc\.pyz"
	pkill -f "krunner-keepassxc"
	autostartpath="~/.local/share/autostart"
	rm -f "${autostartpath}/krunner-keepassxc_autostart.desktop"
fi


rm -f "${dbusplugins_path}/krunner-keepassxc.desktop"
rm -f "$HOME/.local/bin/krunner-keepassxc"
# old version
rm -f "$HOME/.local/bin/krunner-keepassxc.pyz"


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
