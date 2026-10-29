from typing import TypedDict

Config = TypedDict('Config', {
	"trigger": str,
	"max_entries": int,
	"icon": str,
	"totp_as_extra_entry": str,
	"idle_timeout": int,
	"autotype": str,
	"autotype_delay": int,
	"clipboard_clear_delay": int
})

Entry = TypedDict('Entry', {
	'label': str,
	# D-Bus object path of the secret item, ':totp' appended for the extra TOTP entries
	'path': str,
	'attributes': dict[str, str]
})
