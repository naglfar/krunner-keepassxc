import subprocess

class Clipboard:
	
	def __init__(self):
		if self._executable_exists("xclip"):
			self.init_xclip_clipboard()
		elif self._executable_exists("xsel"):
			self.init_xsel_clipboard()
			
	def copy(self, text, primary=False):
		raise NotImplementedError
		
	def paste(self, text, primary=False):
		raise NotImplementedError
	
	def _executable_exists(self, name):
		return subprocess.call(['which', name], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

	def init_xclip_clipboard(self):
		DEFAULT_SELECTION='c'
		PRIMARY_SELECTION='p'
		
		def copy_xclip(text, primary=False):
			selection=DEFAULT_SELECTION
			if primary:
				selection=PRIMARY_SELECTION
			p = subprocess.Popen(['xclip', '-selection', selection], stdin=subprocess.PIPE, close_fds=True)
			p.communicate(input=text.encode('utf-8'))
		
		def paste_xclip(primary=False):
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
		
		self.copy, self.paste = copy_xclip, paste_xclip
		
	def init_xsel_clipboard(self):
		DEFAULT_SELECTION='-b'
		PRIMARY_SELECTION='-p'

		def copy_xsel(text, primary=False):
			selection_flag = DEFAULT_SELECTION
			if primary:
				selection_flag = PRIMARY_SELECTION
			p = subprocess.Popen(['xsel', selection_flag, '-i'], stdin=subprocess.PIPE, close_fds=True)
			p.communicate(input=text.encode('utf-8'))

		def paste_xsel(primary=False):
			selection_flag = DEFAULT_SELECTION
			if primary:
				selection_flag = PRIMARY_SELECTION
			p = subprocess.Popen(['xsel', selection_flag, '-o'], stdout=subprocess.PIPE, close_fds=True)
			stdout, stderr = p.communicate()
			return stdout.decode('utf-8')

		self.copy, self.paste = copy_xsel, paste_xsel