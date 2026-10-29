import os
import shutil
import subprocess
import sys
from collections.abc import Callable

import dbus


class Clipboard:

	can_clip: bool

	def __init__(self):
		self.check_executables()

	def check_executables(self):
		copy, paste = None, None
		self.can_clip = True
		self.bus = dbus.SessionBus()

		try:
			self.klipper = self.bus.get_object('org.kde.klipper', '/klipper')
			copy = self.init_klipper_clipboard()

		except dbus.exceptions.DBusException:

			if self._executable_exists("xclip"):
				copy, paste = self.init_xclip_clipboard()
			elif self._executable_exists("xsel"):
				copy, paste = self.init_xsel_clipboard()
			else:
				self.can_clip = False

		# Wayland: wl-copy --sensitive marks the content as a password (x-kde-passwordManagerHint),
		# so klipper and other clipboard managers keep it out of their history.
		# The previous method stays as fallback in case wl-copy fails.
		if self._wl_copy_sensitive_supported():
			copy = self.init_wl_copy_clipboard(fallback=copy)
			self.can_clip = True

		# FIXME: mypy issue #2427
		if copy:
			self.copy = copy
		if paste:
			self.paste = paste

	def copy(self, text: str, primary: bool=False):
		raise NotImplementedError

	def paste(self, text: str, primary: bool=False):
		raise NotImplementedError

	def _executable_exists(self, name: str):
		return subprocess.call(['which', name], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	@staticmethod
	def _wl_copy_sensitive_supported() -> bool:
		"""Wayland session and wl-copy >= 2.3.0 (knows --sensitive)"""
		if not os.environ.get('WAYLAND_DISPLAY') or not shutil.which('wl-copy'):
			return False
		try:
			result = subprocess.run(['wl-copy', '--help'], capture_output=True, text=True, timeout=5, check=False)
		except (OSError, subprocess.SubprocessError):
			return False
		return '--sensitive' in result.stdout + result.stderr

	def init_wl_copy_clipboard(self, fallback: Callable | None) -> Callable:

		def copy_wl(text: str, primary: bool=False):
			# wl-copy buffers stdin in a temp file (unlinked right away), keep it on the
			# per-user tmpfs instead of a possibly disk backed /tmp
			env = dict(os.environ)
			runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
			if runtime_dir and os.path.isdir(runtime_dir):
				env['TMPDIR'] = runtime_dir
			# explicit type: no content sniffing via xdg-mime on the secret
			args = ['wl-copy', '--sensitive', '--type', 'text/plain;charset=utf-8']
			if primary:
				args.append('--primary')
			try:
				# wl-copy forks into the background to serve the clipboard, so its output must not
				# be connected to pipes we wait on; the value goes via stdin, never via argv
				result = subprocess.run(args, input=text.encode('utf-8'), stdout=subprocess.DEVNULL,
					stderr=subprocess.DEVNULL, env=env, timeout=5, check=False)
				if result.returncode == 0:
					return
				error = f'wl-copy exited with {result.returncode}'
			except (OSError, subprocess.SubprocessError) as e:
				error = f'wl-copy failed: {e}'
			if fallback is None:
				raise RuntimeError(error)
			print(f'{error}, falling back', file=sys.stderr, flush=True)
			fallback(text, primary)

		return copy_wl

	def init_klipper_clipboard(self) -> Callable:

		def copy_klipper(text: str, primary: bool=False):
			klipper = dbus.Interface(self.klipper, dbus_interface='org.kde.klipper.klipper')
			klipper.setClipboardContents(text)

		return copy_klipper

	def init_xclip_clipboard(self) -> tuple[Callable,Callable]:
		DEFAULT_SELECTION: str = 'c'
		PRIMARY_SELECTION: str = 'p'

		def copy_xclip(text: str, primary: bool=False):
			selection = DEFAULT_SELECTION
			if primary:
				selection = PRIMARY_SELECTION
			p = subprocess.Popen(['xclip', '-selection', selection], stdin=subprocess.PIPE, close_fds=True)
			_stdout, stderr = p.communicate(input=text.encode('utf-8'))
			if stderr:
				print(stderr, file=sys.stderr)

		def paste_xclip(primary: bool=False) -> str:
			selection = DEFAULT_SELECTION
			if primary:
				selection = PRIMARY_SELECTION
			p = subprocess.Popen(['xclip', '-selection', selection, '-o'],
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					close_fds=True)
			stdout, _stderr = p.communicate()
			# Intentionally ignore extraneous output on stderr when clipboard is empty
			return stdout.decode('utf-8')

		return copy_xclip, paste_xclip

	def init_xsel_clipboard(self) -> tuple[Callable,Callable]:
		DEFAULT_SELECTION: str = '-b'
		PRIMARY_SELECTION: str = '-p'

		def copy_xsel(text: str, primary: bool=False):
			selection_flag = DEFAULT_SELECTION
			if primary:
				selection_flag = PRIMARY_SELECTION
			p = subprocess.Popen(['xsel', selection_flag, '-i'], stdin=subprocess.PIPE, close_fds=True)
			_stdout, stderr = p.communicate(input=text.encode('utf-8'))
			if stderr:
				print(stderr, file=sys.stderr)

		def paste_xsel(primary: bool=False):
			selection_flag = DEFAULT_SELECTION
			if primary:
				selection_flag = PRIMARY_SELECTION
			p = subprocess.Popen(['xsel', selection_flag, '-o'], stdout=subprocess.PIPE, close_fds=True)
			stdout, _stderr = p.communicate()
			return stdout.decode('utf-8')

		return copy_xsel, paste_xsel
