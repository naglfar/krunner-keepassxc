from typing import Dict, List, TypedDict
from dbus import ObjectPath

Config = TypedDict('Config', {
	"trigger": str,
	"max_entries": int,
	"icon": str,
	"totp_as_extra_entry": str
})

Entry = TypedDict('Entry', {
	'label': str,
	'path': ObjectPath,
	'attributes': Dict[str, str]
})
