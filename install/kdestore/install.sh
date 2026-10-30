#!/bin/bash
# Installs krunner-keepassxc for the current user. Run it from the extracted store archive,
# KNewStuff ("Get New Plugins…" in the Plasma Search settings) does this automatically.
set -u -o pipefail

# work relative to this script, not to the current directory
cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" || { echo "error: can't change into the installer directory" >&2; exit 1; }
# shellcheck source=common.sh
. ./common.sh 2>/dev/null || { echo "error: common.sh is missing, please extract the complete archive" >&2; exit 1; }

refuse_root

# check the package before changing anything, so a broken download leaves the old installation intact
for file in krunner-keepassxc krunner-keepassxc.desktop "$SERVICE_NAME.service"; do
	[ -f "$file" ] || die "$file is missing, please extract the complete archive"
done

# a systemd unit of a previous version would keep restarting the old binary
cleanup_legacy

install_file krunner-keepassxc "$BIN" 755 || die "could not install $BIN"
info "installed $BIN"

install_file krunner-keepassxc.desktop "$DESKTOP_FILE" 644 || die "could not install $DESKTOP_FILE"
sed "s|##exec##|$(sed_escape "$(dbus_exec_line)")|" "$SERVICE_NAME.service" | write_file "$DBUS_SERVICE_FILE" 644 \
	|| die "could not install $DBUS_SERVICE_FILE"
info "installed the krunner plugin and its D-Bus activation file"

# activate: let the bus know the activation file first, then stop a still running (old) instance,
# the next search starts the new one; stopping earlier would allow a search in between to start the old one again
reload_session_bus
stop_running_instance
reload_krunner_plugins

check_wl_clipboard

info "done, krunner-keepassxc gets started automatically on the first search"
info "settings: ${XDG_CONFIG_HOME:-$HOME/.config}/krunner-keepassxc/config (created on the first search, changes apply right away)"
