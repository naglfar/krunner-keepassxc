#!/bin/bash
# Removes krunner-keepassxc of the current user, KNewStuff runs this when uninstalling or
# updating the plugin. The config file (~/.config/krunner-keepassxc) is kept.
set -u

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" || { echo "error: can't change into the installer directory" >&2; exit 1; }
# shellcheck source=common.sh
. ./common.sh 2>/dev/null || { echo "error: common.sh is missing, please extract the complete archive" >&2; exit 1; }

refuse_root

# activation file first, so no search can start the service again in the meantime
failed=0
for file in "$DBUS_SERVICE_FILE" "$DESKTOP_FILE" "$BIN"; do
	if ! rm -f "$file"; then
		warn "could not remove $file"
		failed=1
	fi
done
cleanup_legacy

reload_session_bus
stop_running_instance
reload_krunner_plugins

if [ "$failed" -ne 0 ]; then
	die "some files could not be removed, see above"
fi
info "removed krunner-keepassxc"
