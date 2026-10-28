from typing import TypedDict

from dbus import ObjectPath

Config = TypedDict('Config', {
	"trigger": str,
	"max_entries": int,
	"icon": str,
	"totp_as_extra_entry": str,
	"idle_timeout": int,
	"autotype": str,
	"autotype_delay": int
})

Entry = TypedDict('Entry', {
	'label': str,
	'path': ObjectPath,
	'attributes': dict[str, str]
})
