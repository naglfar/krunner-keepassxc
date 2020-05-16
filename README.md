# krunner-keepassxc

A small krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.
Includes a .desktop file for installing the plugin in krunner aswell as a systemd .service template so the plugin can run in background.

Requires xclip or xsel to be installed for copying to clipboard, keepass has to be configured for secret service access (in both general and database settings).
