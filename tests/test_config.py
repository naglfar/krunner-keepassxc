import configparser
import contextlib
import importlib
import io
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

	def touch(self) -> None:
		"""make sure the modification time differs, some file systems are coarse"""
		stat = self.file.stat()
		os.utime(self.file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

	def reload(self) -> bool:
		"""True if new settings were applied"""
		with contextlib.redirect_stdout(io.StringIO()):
			return self.module.reload_if_changed() == 'reloaded'

	def test_reload_only_after_a_change(self) -> None:
		self.assertEqual(self.module.reload_if_changed(), 'unchanged')  # nothing read yet
		self.module.read_config()
		self.assertFalse(self.reload())
		self.file.write_text(self.file.read_text().replace('max_entries = 5', 'max_entries = 9'))
		self.touch()
		self.assertTrue(self.reload())
		self.assertEqual(self.module.config['max_entries'], 9)
		self.assertFalse(self.reload())

	def test_reload_updates_the_dict_in_place(self) -> None:
		config = self.module.read_config()
		self.file.write_text(self.file.read_text().replace('trigger = \n', 'trigger = kp\n'))
		self.touch()
		self.reload()
		self.assertIs(config, self.module.config)
		self.assertEqual(config['trigger'], 'kp ')

	def test_removed_option_falls_back_to_the_default(self) -> None:
		self.write('[DEFAULT]\nmax_entries = 9\n')
		self.assertEqual(self.module.read_config()['max_entries'], 9)
		self.file.write_text(self.file.read_text().replace('max_entries = 9\n', ''))
		self.touch()
		self.reload()
		self.assertEqual(self.module.config['max_entries'], 5)
		self.assertIn('max_entries = 5', self.file.read_text())  # added again

	def test_invalid_file_keeps_the_previous_settings(self) -> None:
		self.write('[DEFAULT]\nmax_entries = 9\n')
		self.module.read_config()
		content = self.file.read_text()
		self.file.write_text('this is not an ini file\n')
		self.touch()
		output = io.StringIO()
		with contextlib.redirect_stdout(output):
			self.assertEqual(self.module.reload_if_changed(), 'invalid')
			self.assertEqual(self.module.reload_if_changed(), 'unchanged')   # reported once, not on every search
		self.assertFalse(self.module.is_valid())
		self.assertEqual(output.getvalue().count('ignoring the invalid config file'), 1)
		self.assertEqual(self.module.config['max_entries'], 9)
		self.assertEqual(self.file.read_text(), 'this is not an ini file\n')  # not touched
		self.file.write_text(content.replace('max_entries = 9', 'max_entries = 3'))
		self.touch()
		self.assertTrue(self.reload())
		self.assertEqual(self.module.config['max_entries'], 3)

	def test_deleted_file_keeps_the_current_settings(self) -> None:
		self.write('[DEFAULT]\nmax_entries = 9\n')
		self.module.read_config()
		self.file.unlink()
		self.assertFalse(self.reload())
		self.assertEqual(self.module.config['max_entries'], 9)

	def test_invalid_number_keeps_the_default(self) -> None:
		self.write('[DEFAULT]\nmax_entries = many\nidle_timeout = 0\n')
		config = self.module.read_config()
		self.assertEqual(config['max_entries'], 5)
		self.assertEqual(config['idle_timeout'], 0)


if __name__ == '__main__':
	unittest.main()
