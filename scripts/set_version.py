#!/usr/bin/env python3
"""
Set the version of krunner-keepassxc: pyproject.toml is the source, the files that can't read
it themselves (krunner's .desktop files, the pip install link in the README) get updated too.

usage: uv run task version 2.2.0
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# file -> (pattern, replacement template), every pattern has to match exactly once
TARGETS = {
	# only a version number, the taskipy task "version" is in the same file
	'pyproject.toml': (r'(?m)^version = "\d[^"]*"$', 'version = "{version}"'),
	'install/krunner-keepassxc.desktop': (r'(?m)^X-KDE-PluginInfo-Version=.*$', 'X-KDE-PluginInfo-Version={version}'),
	'install/kdestore/krunner-keepassxc.desktop': (r'(?m)^X-KDE-PluginInfo-Version=.*$', 'X-KDE-PluginInfo-Version={version}'),
	'README.md': (
		r'releases/download/[^/\s]+/krunner_-_keepassxc-[^/\s]+-py3-none-any\.whl',
		'releases/download/{version}/krunner_-_keepassxc-{version}-py3-none-any.whl',
	),
}


def main() -> int:
	if len(sys.argv) != 2 or not re.fullmatch(r'\d+\.\d+\.\d+([.-]?[0-9A-Za-z.]+)?', sys.argv[1]):
		print(__doc__.strip(), file=sys.stderr)
		return 2
	version = sys.argv[1]
	updates = {}
	for name, (pattern, template) in TARGETS.items():
		text = (ROOT / name).read_text(encoding='utf-8')
		new, count = re.subn(pattern, template.format(version=version), text)
		if count != 1:
			print(f'{name}: expected exactly one match, found {count}, nothing changed', file=sys.stderr)
			return 1
		updates[name] = new
	# only write once every file matched
	for name, text in updates.items():
		(ROOT / name).write_text(text, encoding='utf-8')
		print(f'{name}: {version}')
	print('run "uv sync" so the installed package metadata has the new version as well')
	return 0


if __name__ == '__main__':
	sys.exit(main())
