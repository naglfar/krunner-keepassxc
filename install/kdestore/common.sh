# shellcheck shell=bash
# shellcheck disable=SC2034 # the variables are used by the scripts sourcing this file
# Shared by install.sh and uninstall.sh (sourced, not executed).
# KNewStuff runs both scripts in a visible terminal, so progress and problems are printed.

SERVICE_NAME="de.naglfar.krunner-keepassxc"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/krunner-keepassxc"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DBUS_SERVICE_FILE="$DATA_HOME/dbus-1/services/$SERVICE_NAME.service"
DESKTOP_FILE="$DATA_HOME/krunner/dbusplugins/krunner-keepassxc.desktop"

has() { command -v "$1" >/dev/null 2>&1; }
info() { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

refuse_root() {
	# everything goes into the user's home, as root it would end up in /root or,
	# with sudo keeping $HOME, leave root owned files the user can't replace later
	if [ "$(id -u)" -eq 0 ]; then
		die "please run this as your normal user, not as root or with sudo"
	fi
}

_tmp_name() { printf '%s/.%s.new.%s' "$(dirname "$1")" "$(basename "$1")" "$$"; }

# install_file SOURCE DEST MODE
# copies to a temporary name next to DEST and renames it into place: never leaves a half written
# file behind, and works while the old binary is still running (overwriting fails with "Text file busy")
install_file() {
	local tmp
	tmp=$(_tmp_name "$2")
	if mkdir -p "$(dirname "$2")" && cp "$1" "$tmp" && chmod "$3" "$tmp" && mv -f "$tmp" "$2"; then
		return 0
	fi
	rm -f "$tmp"
	return 1
}

# write_file DEST MODE < content
write_file() {
	local tmp
	tmp=$(_tmp_name "$1")
	if mkdir -p "$(dirname "$1")" && cat > "$tmp" && chmod "$2" "$tmp" && mv -f "$tmp" "$1"; then
		return 0
	fi
	rm -f "$tmp"
	return 1
}

# escape a string for the replacement part of sed "s|...|...|"
sed_escape() { printf '%s' "$1" | sed -e 's/[\\&|]/\\&/g'; }

# Exec line of the D-Bus activation file, the path quoted (dbus-daemon and dbus-broker both
# split Exec like a shell), so a home directory with spaces works
dbus_exec_line() {
	local path=${BIN//\\/\\\\}
	path=${path//\"/\\\"}
	printf '"%s" run' "$path"
}

reload_session_bus() {
	# not every bus watches its service directories (dbus-broker doesn't)
	if has busctl && busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig >/dev/null 2>&1; then
		return 0
	fi
	if has dbus-send && dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
			org.freedesktop.DBus.ReloadConfig >/dev/null 2>&1; then
		return 0
	fi
	warn "could not reload the session bus configuration, the change takes effect after logging out and in again"
	return 1
}

# stop the running instance: exactly the process that owns the service's D-Bus name
# (old versions use the same name), instead of matching command lines
stop_running_instance() {
	local pid=""
	if has busctl; then
		pid=$(busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus \
			GetConnectionUnixProcessID s "$SERVICE_NAME" 2>/dev/null | cut -d' ' -f2)
	elif has dbus-send; then
		pid=$(dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus \
			org.freedesktop.DBus.GetConnectionUnixProcessID string:"$SERVICE_NAME" 2>/dev/null | awk '/uint32/ {print $2}')
	fi
	case "$pid" in
		''|*[!0-9]*) return 0 ;;	# not running (or no D-Bus tools)
	esac
	if kill "$pid" 2>/dev/null; then
		info "stopped the running instance (pid $pid)"
	fi
}

reload_krunner_plugins() {
	# the same signal the "Plasma Search" settings send: krunner and the plasmashell search
	# reload their plugin list, no restart required
	if has busctl && busctl --user emit /krunnerrc org.kde.kconfig.notify ConfigChanged 'a{saay}' 1 Plugins 0 >/dev/null 2>&1; then
		info "reloaded the krunner plugin list"
		return 0
	fi
	# fallback: quit krunner, it is started again on demand (D-Bus activation) with the new plugin list
	if has kquitapp6 && kquitapp6 krunner >/dev/null 2>&1; then
		:
	elif has kquitapp5 && kquitapp5 krunner >/dev/null 2>&1; then
		:
	else
		pkill -x krunner
	fi
	info "restarted krunner, the search in the application launcher picks up the change after the next login"
}

# Wayland: secrets are only kept out of klipper's clipboard history when copied with
# wl-copy --sensitive (wl-clipboard >= 2.3.0), otherwise the plugin falls back to klipper
check_wl_clipboard() {
	if [ -z "${WAYLAND_DISPLAY:-}" ] && [ "${XDG_SESSION_TYPE:-}" != "wayland" ]; then
		return 0
	fi
	local problem action
	if ! has wl-copy; then
		problem="wl-clipboard is not installed"
		action="install"
	elif ! wl-copy --help 2>&1 | grep -q -- '--sensitive'; then
		problem="the installed wl-clipboard is too old, version 2.3.0 or newer is recommended"
		action="update"
	else
		return 0
	fi
	info ""
	info "note: $problem."
	info "  Please $action it using your package manager (the package is called wl-clipboard)."
	info "  Without it copied passwords end up in Klipper's clipboard history, which is also saved to disk."
	info ""
}

# previous installation methods: systemd user unit or autostart entry
cleanup_legacy() {
	if has systemctl && systemctl --user cat krunner-keepassxc.service >/dev/null 2>&1; then
		systemctl --user disable --now krunner-keepassxc.service >/dev/null 2>&1 \
			&& info "removed the systemd user service of a previous version"
	fi
	rm -f "$DATA_HOME/systemd/user/krunner-keepassxc.service" \
		"$HOME/.config/systemd/user/krunner-keepassxc.service" \
		"$HOME/.config/autostart/krunner-keepassxc_autostart.desktop" \
		"$DATA_HOME/autostart/krunner-keepassxc_autostart.desktop" \
		"$BIN_DIR/krunner-keepassxc.pyz"
	if has systemctl; then
		systemctl --user daemon-reload >/dev/null 2>&1
	fi
	return 0
}
