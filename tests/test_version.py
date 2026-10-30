import re
import tomllib
import unittest
from pathlib import Path

from krunner_keepassxc import __version__

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']


class VersionTests(unittest.TestCase):
	"""pyproject.toml is the source, the other files are updated by scripts/set_version.py"""

	def test_package_version(self) -> None:
		if __version__ == '0+unknown':
			self.skipTest('package not installed, run the tests with "uv run task tests"')
		self.assertEqual(__version__, VERSION, 'installed metadata is outdated, run "uv sync"')

	def test_desktop_files(self) -> None:
		for name in ('install/krunner-keepassxc.desktop', 'install/kdestore/krunner-keepassxc.desktop'):
			with self.subTest(file=name):
				text = (ROOT / name).read_text(encoding='utf-8')
				self.assertIn(f'X-KDE-PluginInfo-Version={VERSION}\n', text)

	def test_readme_pip_link(self) -> None:
		links = re.findall(r'releases/download/([^/\s]+)/krunner_-_keepassxc-([^/\s]+)-py3-none-any\.whl',
			(ROOT / 'README.md').read_text(encoding='utf-8'))
		self.assertEqual(links, [(VERSION, VERSION)])


if __name__ == '__main__':
	unittest.main()
