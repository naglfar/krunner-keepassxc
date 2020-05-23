import sys
import subprocess

from typing import Tuple, Callable

class Clipboard:

	def __init__(self):
		if self._executable_exists("xclip"):
			copy, paste = self.init_xclip_clipboard()
		elif self._executable_exists("xsel"):
			copy, paste = self.init_xsel_clipboard()

		# FIXME: mypy issue #2427
		if copy: setattr(self, 'copy', copy)
		if paste: setattr(self, 'paste', paste)

	def copy(self, text: str, primary: bool=False):
		raise NotImplementedError

	def paste(self, text: str, primary: bool=False):
		raise NotImplementedError

	def _executable_exists(self, name: str):
		return subprocess.call(['which', name], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def init_xclip_clipboard(self) -> Tuple[Callable,Callable]:
		DEFAULT_SELECTION:str = 'c'
		PRIMARY_SELECTION:str = 'p'

		def copy_xclip(text: str, primary: bool=False):
			selection=DEFAULT_SELECTION
			if primary:
				selection=PRIMARY_SELECTION
			p = subprocess.Popen(['xclip', '-selection', selection], stdin=subprocess.PIPE, close_fds=True)
			stdout, stderr = p.communicate(input=text.encode('utf-8'))
			if stderr: print(stderr, file=sys.stderr)

		def paste_xclip(primary: bool=False) -> str:
			selection=DEFAULT_SELECTION
			if primary:
				selection=PRIMARY_SELECTION
			p = subprocess.Popen(['xclip', '-selection', selection, '-o'],
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					close_fds=True)
			stdout, stderr = p.communicate()
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
			stdout, stderr = p.communicate(input=text.encode('utf-8'))
			if stderr: print(stderr, file=sys.stderr)

		def paste_xsel(primary: bool=False):
			selection_flag = DEFAULT_SELECTION
			if primary:
				selection_flag = PRIMARY_SELECTION
			p = subprocess.Popen(['xsel', selection_flag, '-o'], stdout=subprocess.PIPE, close_fds=True)
			stdout, stderr = p.communicate()
			return stdout.decode('utf-8')

		return copy_xsel, paste_xsel
