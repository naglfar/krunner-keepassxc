import sys
import subprocess
import dbus

from typing import Tuple, Callable

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

		except dbus.exceptions.DBusException as e:

			if self._executable_exists("xclip"):
				copy, paste = self.init_xclip_clipboard()
			elif self._executable_exists("xsel"):
				copy, paste = self.init_xsel_clipboard()
			else:
				self.can_clip = False

		# FIXME: mypy issue #2427
		if copy:
			setattr(self, 'copy', copy)
		if paste:
			setattr(self, 'paste', paste)

	def copy(self, text: str, primary: bool=False):
		raise NotImplementedError

	def paste(self, text: str, primary: bool=False):
		raise NotImplementedError

	def _executable_exists(self, name: str):
		return subprocess.call(['which', name], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def init_klipper_clipboard(self) -> Callable:

		def copy_klipper(text: str, primary: bool=False):
			klipper = dbus.Interface(self.klipper, dbus_interface='org.kde.klipper.klipper')
			klipper.setClipboardContents(text)

		return copy_klipper

	def init_xclip_clipboard(self) -> Tuple[Callable,Callable]:
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

	def init_xsel_clipboard(self) -> Tuple[Callable,Callable]:
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
