"""
Plugin configuration: defaults, comments and reading ~/.config/krunner-keepassxc/config

The file is read with the plain stdlib ConfigParser (comments are skipped,
no interpolation). Missing options are added with their comment and default
value at the end of the [DEFAULT] section, the rest of the file is never
rewritten, so comments and formatting of the user are preserved.

reload_if_changed() re-reads the file when it was modified since, the service
calls it on every krunner request, so edits apply without a restart.
"""
import configparser
import os
from typing import cast

from xdg import xdg_config_home

from .types import Config

app_name = 'krunner-keepassxc'
DEFAULTS: Config = {
	"trigger": "",
	"max_entries": 5,
	"icon": "object-unlocked",
	"totp_as_extra_entry": "True",
	"idle_timeout": 600,
	"autotype": "False",
	"autotype_delay": 300,
	"clipboard_clear_delay": 10
}
# the current settings, updated in place by read_config()
config: Config = cast(Config, dict(DEFAULTS))
config_numbers = [ 'max_entries', 'idle_timeout', 'autotype_delay', 'clipboard_clear_delay' ]
config_comments = {
	"trigger": "characters to trigger password lookup, can be empty (default)",
	"max_entries": "maximum number of entries to list (default: 5)",
	"icon": "the icon to use, you can find possible values in /usr/share/icons/<your theme>/ (default: object-unlocked)",
	"totp_as_extra_entry": "if you have TOTP entries they will show up as extra list entries instead of another action icon (true / false)",
	"idle_timeout": "seconds without krunner requests after which the service exits, it gets restarted on demand via D-Bus activation (0 = never exit, default: 600)",
	"autotype": "type the values into the focused window instead of copying them to the clipboard, needs libei on Wayland or libXtst on X11 (true / false)",
	"autotype_delay": "milliseconds to wait before typing so krunner can close and the previous window regains focus (default: 300)",
	"clipboard_clear_delay": "seconds after which the clipboard is emptied after copying a value, regardless of what it contains by then (0 = never, default: 10)"
}


def _config_entry(key: str, value: object) -> str:
	return f'# {config_comments[key]}\n{key} = {value}\n\n'


def _add_config_entries(filename: str, keys: list[str]) -> None:
	"""
	add the given keys with their comment and default value to the [DEFAULT] section,
	everything else in the file (comments, order, formatting) stays untouched
	"""
	# always the defaults, config may hold the previous values when the file is re-read
	entries = ''.join(_config_entry(k, DEFAULTS[k]) for k in keys)	# type: ignore[literal-required]
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


# file name and state (see _file_state) at the last read, and whether the file was valid then
_loaded: tuple[str, tuple[int, int, int] | None] | None = None
_valid = True


def config_file() -> str:
	return os.path.join(xdg_config_home(), app_name, 'config')


def _file_state(filename: str) -> tuple[int, int, int] | None:
	"""
	modification time, size and inode: the time alone can miss quick successive edits on file
	systems with coarse timestamps, many editors replace the file on saving (new inode)
	"""
	try:
		stat = os.stat(filename)
	except OSError:
		return None
	return stat.st_mtime_ns, stat.st_size, stat.st_ino


def read_config() -> Config:
	"""
	Read the config file into config (updated in place) and add missing options to the file.
	An invalid file is reported and ignored, the previous settings (or the defaults) stay in effect.
	"""
	global _loaded, _valid
	filename = config_file()
	# plain ConfigParser, comments are skipped on reading; no interpolation so '%' is just a character
	parser = configparser.ConfigParser(interpolation=None)
	try:
		parser.read(filename, encoding='utf-8')
	except (configparser.Error, UnicodeDecodeError) as e:
		print(f'ignoring the invalid config file {filename}: {e}', flush=True)
		_loaded, _valid = (filename, _file_state(filename)), False
		return config
	section = parser[configparser.DEFAULTSECT]

	missing = [k for k in DEFAULTS if k not in section]
	if missing:
		_add_config_entries(filename, missing)

	# start from the defaults, so options removed from the file fall back to them
	# config is a TypedDict, the keys are only known at runtime here
	values = cast(dict[str, object], config)
	values.clear()
	values.update(DEFAULTS)
	for k, raw in section.items():
		if k not in DEFAULTS:
			continue
		value: str | int = raw
		if k in config_numbers:
			try:
				value = int(raw)
			except ValueError:
				# invalid number, keep the default
				continue
		values[k] = value

	if len(config['trigger']) > 0: config['trigger'] += ' '
	_loaded, _valid = (filename, _file_state(filename)), True
	return config


def reload_if_changed() -> bool:
	"""re-read the config file if it was modified since the last read, True if new settings were applied"""
	if _loaded is None:
		return False
	filename, state = _loaded
	current = _file_state(filename)
	if current is None or current == state:
		# unchanged, or deleted (then keep the current settings)
		return False
	read_config()
	if not _valid:
		return False
	print(f'reloaded the config file {filename}', flush=True)
	return True
