"""
Clipboard access for the runner, all asynchronous.

Backends, in order of preference:

* Wayland with wl-copy >= 2.3.0: ``wl-copy --sensitive`` marks the value as a password
  (x-kde-passwordManagerHint), so klipper and other clipboard managers keep it out of
  their history; the next backend stays as fallback in case wl-copy fails
* klipper via D-Bus (dbus-fast, the runner's bus connection)

Without either nothing can be copied (can_clip is False).
"""
import asyncio
import os
import shutil
import sys
from collections.abc import Awaitable, Callable

from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

KLIPPER_BUS = 'org.kde.klipper'
KLIPPER_PATH = '/klipper'
KLIPPER_IFACE = 'org.kde.klipper.klipper'

SUBPROCESS_TIMEOUT = 5.0

# backend functions, all called positionally: (text, primary) / (primary)
CopyFunc = Callable[[str, bool], Awaitable[None]]
ClearFunc = Callable[[bool], Awaitable[None]]


async def _run(args: list[str], stdin: bytes | None = None, env: dict[str, str] | None = None,
		capture: bool = False) -> tuple[int, bytes]:
	"""
	run a command, returns (exit code, stdout)
	stdout/stderr are not attached to pipes unless captured: wl-copy forks into the background
	to serve the clipboard and would otherwise keep the pipes (and us) waiting
	"""
	process = await asyncio.create_subprocess_exec(
		*args,
		stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
		stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
		stderr=asyncio.subprocess.DEVNULL,
		env=env,
	)
	try:
		stdout, _stderr = await asyncio.wait_for(process.communicate(stdin), SUBPROCESS_TIMEOUT)
	except TimeoutError:
		process.kill()
		await process.wait()
		raise
	return process.returncode or 0, stdout or b''


class Clipboard:

	can_clip: bool
	_copy: CopyFunc | None
	_clear: ClearFunc | None

	def __init__(self, bus: MessageBus) -> None:
		self.bus = bus
		self.can_clip = False
		self._checked = False
		self._copy = self._clear = None

	async def check_executables(self) -> None:
		"""pick the backend, can be called again (e.g. after klipper or wl-copy became available)"""
		copy: CopyFunc | None = None
		clear: ClearFunc | None = None
		self.can_clip = False

		if await self._klipper_available():
			copy, clear = self._copy_klipper, self._clear_klipper
			self.can_clip = True

		if await self._wl_copy_sensitive_supported():
			copy = self._make_wl_copy(fallback=copy)
			clear = self._make_wl_clear(fallback=clear)
			self.can_clip = True

		self._copy, self._clear = copy, clear
		self._checked = True

	async def _ensure_checked(self) -> None:
		if not self._checked:
			await self.check_executables()

	async def copy(self, text: str, primary: bool = False) -> None:
		await self._ensure_checked()
		if self._copy is None:
			raise NotImplementedError
		await self._copy(text, primary)

	async def clear(self, primary: bool = False) -> None:
		"""empty the clipboard, whatever it currently contains"""
		await self._ensure_checked()
		if self._clear is None:
			raise NotImplementedError
		await self._clear(primary)

	# klipper

	async def _klipper_available(self) -> bool:
		reply = await self.bus.call(Message(
			destination='org.freedesktop.DBus', path='/org/freedesktop/DBus', interface='org.freedesktop.DBus',
			member='NameHasOwner', signature='s', body=[KLIPPER_BUS]))
		return reply is not None and reply.message_type == MessageType.METHOD_RETURN and bool(reply.body[0])

	async def _call_klipper(self, member: str, signature: str = '', body: list | None = None) -> None:
		reply = await self.bus.call(Message(
			destination=KLIPPER_BUS, path=KLIPPER_PATH, interface=KLIPPER_IFACE,
			member=member, signature=signature, body=body or []))
		if reply is None or reply.message_type == MessageType.ERROR:
			error = reply.body[0] if reply is not None and reply.body else ''
			raise RuntimeError(f'klipper {member} failed: {reply.error_name if reply else "no reply"} {error}')

	async def _copy_klipper(self, text: str, primary: bool = False) -> None:
		await self._call_klipper('setClipboardContents', 's', [text])

	async def _clear_klipper(self, primary: bool = False) -> None:
		# clears the current clipboard (and selection), not klipper's history
		await self._call_klipper('clearClipboardContents')

	# wl-copy

	@staticmethod
	async def _wl_copy_sensitive_supported() -> bool:
		"""Wayland session and wl-copy >= 2.3.0 (knows --sensitive)"""
		if not os.environ.get('WAYLAND_DISPLAY') or not shutil.which('wl-copy'):
			return False
		try:
			_code, output = await _run(['wl-copy', '--help'], capture=True)
		except (OSError, TimeoutError):
			return False
		return b'--sensitive' in output

	@staticmethod
	def _make_wl_copy(fallback: CopyFunc | None) -> CopyFunc:

		async def copy_wl(text: str, primary: bool = False) -> None:
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
				# the value goes via stdin, never via argv
				code, _stdout = await _run(args, stdin=text.encode('utf-8'), env=env)
				if code == 0:
					return
				error = f'wl-copy exited with {code}'
			except (OSError, TimeoutError) as e:
				error = f'wl-copy failed: {e!r}'
			if fallback is None:
				raise RuntimeError(error)
			print(f'{error}, falling back', file=sys.stderr, flush=True)
			await fallback(text, primary)

		return copy_wl

	@staticmethod
	def _make_wl_clear(fallback: ClearFunc | None) -> ClearFunc:

		async def clear_wl(primary: bool = False) -> None:
			args = ['wl-copy', '--clear'] + (['--primary'] if primary else [])
			try:
				code, _stdout = await _run(args)
				if code == 0:
					return
				error = f'wl-copy --clear exited with {code}'
			except (OSError, TimeoutError) as e:
				error = f'wl-copy --clear failed: {e!r}'
			if fallback is None:
				raise RuntimeError(error)
			print(f'{error}, falling back', file=sys.stderr, flush=True)
			await fallback(primary)

		return clear_wl
