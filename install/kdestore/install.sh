#!/bin/bash
pwd=$(pwd)

bin="$HOME/.local/bin"
mkdir -p "${bin}"
# remove old version if exists
rm -f "$bin/krunner-keepassxc.pyz"
cp "$pwd/krunner-keepassxc" "$bin/"
chmod +x "$bin/krunner-keepassxc"
exec="$bin/krunner-keepassxc run"

data_home="${XDG_DATA_HOME:-$HOME/.local/share}"

# krunner plugin
dbusplugins_path="$data_home/krunner/dbusplugins"
mkdir -p "${dbusplugins_path}"
cp krunner-keepassxc.desktop "${dbusplugins_path}/"

# D-Bus activation file, the session bus starts the service on demand
dbusservices_path="$data_home/dbus-1/services"
mkdir -p "${dbusservices_path}"
sed "s|##exec##|${exec}|" "de.naglfar.krunner-keepassxc.service" > "${dbusservices_path}/de.naglfar.krunner-keepassxc.service"

# clean up previous installations (systemd user unit / autostart entry)
if command -v systemctl >/dev/null 2>&1 && systemctl --user cat krunner-keepassxc.service >/dev/null 2>&1; then
	systemctl --user disable --now krunner-keepassxc.service >/dev/null 2>&1
fi
rm -f "$data_home/systemd/user/krunner-keepassxc.service" \
	"$HOME/.config/systemd/user/krunner-keepassxc.service" \
	"$HOME/.config/autostart/krunner-keepassxc_autostart.desktop" \
	"$data_home/autostart/krunner-keepassxc_autostart.desktop"
command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1

# stop a still running instance so the new binary gets activated on next use
pkill -f "krunner-keepassxc(\.pyz)? run"

# make the session bus pick up the new service file
if command -v busctl >/dev/null 2>&1; then
	busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig >/dev/null 2>&1
elif command -v dbus-send >/dev/null 2>&1; then
	dbus-send --session --type=method_call --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ReloadConfig >/dev/null 2>&1
fi

# make krunner reload its plugin list, no restart required
if command -v busctl >/dev/null 2>&1 && \
	busctl --user emit /krunnerrc org.kde.kconfig.notify ConfigChanged 'a{saay}' 1 Plugins 0 >/dev/null 2>&1; then
	:
else
	# fallback: restart krunner
	if command -v kquitapp6 >/dev/null 2>&1; then
		kquitapp6 krunner >/dev/null 2>&1 || pkill -x krunner
	elif command -v kquitapp5 >/dev/null 2>&1; then
		kquitapp5 krunner >/dev/null 2>&1 || pkill -x krunner
	else
		pkill -x krunner
	fi
	sleep 1
	if command -v kstart6 >/dev/null 2>&1; then
		kstart6 krunner >/dev/null 2>&1
	elif command -v kstart5 >/dev/null 2>&1; then
		kstart5 krunner >/dev/null 2>&1
	else
		nohup krunner >/dev/null 2>&1 &
	fi
fi
