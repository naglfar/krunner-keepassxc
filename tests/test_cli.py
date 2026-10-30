import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from krunner_keepassxc import __version__

SRC = Path(__file__).resolve().parent.parent / 'src'


class CliTests(unittest.TestCase):

	def run_cli(self, *args: str, config_home: str) -> subprocess.CompletedProcess[str]:
		env = {**os.environ, 'XDG_CONFIG_HOME': config_home, 'PYTHONPATH': str(SRC), 'PYTHONDONTWRITEBYTECODE': '1'}
		return subprocess.run([sys.executable, '-m', 'krunner_keepassxc', *args],
			capture_output=True, text=True, env=env, timeout=30, check=False)

	def test_version(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			for option in ('--version', '-V'):
				with self.subTest(option=option):
					result = self.run_cli(option, config_home=tmp)
					self.assertEqual(result.returncode, 0, result.stderr)
					self.assertEqual(result.stdout.strip(), f'krunner-keepassxc {__version__}')
			# neither --version nor --help create the config file
			self.run_cli('--help', config_home=tmp)
			self.assertFalse((Path(tmp) / 'krunner-keepassxc').exists())


if __name__ == '__main__':
	unittest.main()
