#!/bin/bash
data_home="${XDG_DATA_HOME:-$HOME/.local/share}"

# stop a running instance
pkill -f "krunner-keepassxc(\.pyz)? run"

rm -f "$data_home/dbus-1/services/de.naglfar.krunner-keepassxc.service"
rm -f "$data_home/krunner/dbusplugins/krunner-keepassxc.desktop"
rm -f "$HOME/.local/bin/krunner-keepassxc"
# old versions
rm -f "$HOME/.local/bin/krunner-keepassxc.pyz"
if command -v systemctl >/dev/null 2>&1 && systemctl --user cat krunner-keepassxc.service >/dev/null 2>&1; then
	systemctl --user disable --now krunner-keepassxc.service >/dev/null 2>&1
fi
rm -f "$data_home/systemd/user/krunner-keepassxc.service" \
	"$HOME/.config/systemd/user/krunner-keepassxc.service" \
	"$HOME/.config/autostart/krunner-keepassxc_autostart.desktop" \
	"$data_home/autostart/krunner-keepassxc_autostart.desktop"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1

if command -v busctl >/dev/null 2>&1; then
	busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig >/dev/null 2>&1
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
