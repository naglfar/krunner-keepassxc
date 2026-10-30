import configparser
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import krunner_keepassxc.config


class ConfigTests(unittest.TestCase):

	def setUp(self) -> None:
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		env = mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': self.tmp.name})
		env.start()
		self.addCleanup(env.stop)
		# fresh defaults, read_config() updates the module's config dict in place
		self.module = importlib.reload(krunner_keepassxc.config)
		self.file = Path(self.tmp.name) / 'krunner-keepassxc' / 'config'

	def write(self, content: str) -> None:
		self.file.parent.mkdir(parents=True)
		self.file.write_text(content, encoding='utf-8')

	def parse(self) -> configparser.SectionProxy:
		parser = configparser.ConfigParser(interpolation=None)
		parser.read(self.file, encoding='utf-8')
		return parser[configparser.DEFAULTSECT]

	def test_first_start_writes_all_options_with_comments(self) -> None:
		config = self.module.read_config()
		content = self.file.read_text(encoding='utf-8')
		self.assertTrue(content.startswith('[DEFAULT]\n'))
		for key, comment in self.module.config_comments.items():
			self.assertIn(f'# {comment}\n{key} = ', content)
		self.assertNotIn('None', content)
		self.assertEqual(set(self.parse()), set(self.module.config))
		self.assertEqual(config['max_entries'], 5)

	def test_complete_file_is_not_rewritten(self) -> None:
		self.module.read_config()
		before = self.file.stat().st_mtime_ns, self.file.read_bytes()
		importlib.reload(self.module).read_config()
		self.assertEqual((self.file.stat().st_mtime_ns, self.file.read_bytes()), before)

	def test_user_content_is_kept_and_missing_options_are_added(self) -> None:
		self.write('[DEFAULT]\n# my own comment, 100% kept\ntrigger = kp\nmax_entries = 7')
		config = self.module.read_config()
		content = self.file.read_text(encoding='utf-8')
		self.assertTrue(content.startswith('[DEFAULT]\n# my own comment, 100% kept\ntrigger = kp\nmax_entries = 7\n'))
		self.assertIn('idle_timeout = ', content)
		self.assertEqual(config['trigger'], 'kp ')  # trailing space added for the trigger
		self.assertEqual(config['max_entries'], 7)

	def test_options_are_added_to_default_not_to_a_later_section(self) -> None:
		self.write('[DEFAULT]\ntrigger = kp\n\n[other]\nfoo = bar\n')
		self.module.read_config()
		parser = configparser.ConfigParser(interpolation=None)
		parser.read(self.file, encoding='utf-8')
		self.assertIn('max_entries', parser.defaults())
		self.assertEqual(parser['other']['foo'], 'bar')
		self.assertTrue(self.file.read_text(encoding='utf-8').rstrip().endswith('[other]\nfoo = bar'))

	def test_default_section_is_added_when_missing(self) -> None:
		self.write('[other]\nfoo = bar\n')
		self.module.read_config()
		self.assertTrue(self.file.read_text(encoding='utf-8').startswith('[DEFAULT]\n'))
		self.assertEqual(set(self.parse()), set(self.module.config))

	def test_invalid_number_keeps_the_default(self) -> None:
		self.write('[DEFAULT]\nmax_entries = many\nidle_timeout = 0\n')
		config = self.module.read_config()
		self.assertEqual(config['max_entries'], 5)
		self.assertEqual(config['idle_timeout'], 0)


if __name__ == '__main__':
	unittest.main()
