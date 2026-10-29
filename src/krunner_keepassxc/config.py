"""
Plugin configuration: defaults, comments and reading ~/.config/krunner-keepassxc/config

The file is read with the plain stdlib ConfigParser (comments are skipped,
no interpolation). Missing options are added with their comment and default
value at the end of the [DEFAULT] section, the rest of the file is never
rewritten, so comments and formatting of the user are preserved.
"""
import configparser
import os
from typing import cast

from xdg import xdg_config_home

from .types import Config

app_name = 'krunner-keepassxc'
config: Config = {
	"trigger": "",
	"max_entries": 5,
	"icon": "object-unlocked",
	"totp_as_extra_entry": "True",
	"idle_timeout": 600,
	"autotype": "False",
	"autotype_delay": 300
}
config_numbers = [ 'max_entries', 'idle_timeout', 'autotype_delay' ]
config_comments = {
	"trigger": "characters to trigger password lookup, can be empty (default)",
	"max_entries": "maximum number of entries to list (default: 5)",
	"icon": "the icon to use, you can find possible values in /usr/share/icons/<your theme>/ (default: object-unlock)",
	"totp_as_extra_entry": "if you have TOTP entries they will show up as extra list entries instead of another action icon (true / false)",
	"idle_timeout": "seconds without krunner requests after which the service exits, it gets restarted on demand via D-Bus activation (0 = never exit, default: 600)",
	"autotype": "type the values into the focused window instead of copying them to the clipboard, needs libei on Wayland or libXtst on X11 (true / false)",
	"autotype_delay": "milliseconds to wait before typing so krunner can close and the previous window regains focus (default: 300)"
}


def _config_entry(key: str, value) -> str:
	return f'# {config_comments[key]}\n{key} = {value}\n\n'


def _add_config_entries(filename: str, keys: list[str]):
	"""
	add the given keys with their comment and default value to the [DEFAULT] section,
	everything else in the file (comments, order, formatting) stays untouched
	"""
	entries = ''.join(_config_entry(k, config[k]) for k in keys)	# type: ignore[literal-required]
	try:
		with open(filename, encoding='utf-8') as file:
			lines = file.readlines()
	except FileNotFoundError:
		lines = []

	header = f'[{configparser.DEFAULTSECT}]'
	default_index = next((i for i, line in enumerate(lines) if line.strip() == header), None)
	if default_index is None:
		# no [DEFAULT] section yet, it has to come before any other section
		lines = [header + '\n', entries, *lines]
	else:
		# insert at the end of the [DEFAULT] section, i.e. before the next section header
		insert = next((i for i in range(default_index + 1, len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
		before = lines[:insert]
		if before and not before[-1].endswith('\n'):
			before[-1] += '\n'
		if before and before[-1].strip():
			before.append('\n')
		lines = [*before, entries, *lines[insert:]]

	os.makedirs(os.path.dirname(filename), exist_ok=True)
	tmp = f'{filename}.tmp'
	with open(tmp, 'w', encoding='utf-8') as file:
		file.writelines(lines)
	os.replace(tmp, filename)


def read_config():
	filename = os.path.join(xdg_config_home(), app_name, 'config')
	# plain ConfigParser, comments are skipped on reading; no interpolation so '%' is just a character
	parser = configparser.ConfigParser(interpolation=None)
	parser.read(filename, encoding='utf-8')
	section = parser[configparser.DEFAULTSECT]

	missing = [k for k in config if k not in section]
	if missing:
		_add_config_entries(filename, missing)

	for k, v in section.items():
		if k in config:
			if k in config_numbers:
				try:
					v = int(cast(int, v))
				except ValueError:
					v = config[k]	# type: ignore
			config[k] = v	# type: ignore

	if len(config['trigger']) > 0: config['trigger'] += ' '
	return config
