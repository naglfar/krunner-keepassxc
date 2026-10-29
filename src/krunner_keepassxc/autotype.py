"""
Auto-type text into the focused window, on Wayland (libei) and X11 (XTEST).

Wayland: permission is obtained through the XDG RemoteDesktop portal (keyboard only),
the portal hands out an EIS file descriptor (``ConnectToEIS``) and the input
is emulated with libei through the python-libei bindings.

* the consent dialog is shown once, afterwards the portal's restore token is
  used (``persist_mode`` = until revoked), the token is stored with mode 0600
* if the compositor offers a TEXT capable device (libei >= 1.6 on both sides)
  the text is sent as UTF-8 and the compositor resolves the keys itself
* otherwise the characters are resolved to evdev keycodes through the XKB
  keymap the compositor sends along with the keyboard device (libxkbcommon
  via ctypes); all characters are resolved before anything is typed, so a
  password is never typed partially

X11: keys are sent with the XTEST extension (libX11 / libXtst via ctypes),
the keymap, active layout group and caps lock state are read from the X
server with libxkbcommon-x11 and resolved the same way as on Wayland.
"""
import asyncio
import ctypes
import ctypes.util
import os
import secrets
from contextlib import suppress

from dbus_fast import Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from xdg import xdg_state_home

try:
	from libei import ei
except ImportError:  # pragma: no cover - optional dependency
	ei = None  # type: ignore[assignment]

PORTAL_BUS = 'org.freedesktop.portal.Desktop'
PORTAL_PATH = '/org/freedesktop/portal/desktop'
IFACE_REMOTE_DESKTOP = 'org.freedesktop.portal.RemoteDesktop'
IFACE_REQUEST = 'org.freedesktop.portal.Request'
IFACE_SESSION = 'org.freedesktop.portal.Session'

DEVICE_KEYBOARD = 1
PERSIST_UNTIL_REVOKED = 2

# evdev keycodes
KEY_LEFTSHIFT = 42
KEY_RIGHTALT = 100
KEY_CAPSLOCK = 58
# keysyms
XK_Shift_L = 0xffe1
XK_ISO_Level3_Shift = 0xfe03
XK_Caps_Lock = 0xffe5
XK_Tab = 0xff09
XK_Return = 0xff0d
XKB_EVDEV_OFFSET = 8


class AutotypeError(Exception):
	pass


def _find_library(name: str, fallback: str) -> str:
	return ctypes.util.find_library(name) or fallback


def backend() -> str | None:
	"""'wayland', 'x11' or None if auto-type can't work in this session"""
	if os.environ.get('WAYLAND_DISPLAY'):
		# XTEST under Wayland would only reach Xwayland windows, so libei or nothing
		return 'wayland' if ei is not None and ei.is_available() else None
	if os.environ.get('DISPLAY'):
		try:
			for name, fallback in _X11_LIBRARIES:
				ctypes.CDLL(_find_library(name, fallback))
		except OSError:
			return None
		return 'x11'
	return None


def is_available() -> bool:
	return backend() is not None


class _TokenStore:

	def __init__(self, app_name: str):
		self.path = os.path.join(str(xdg_state_home()), app_name, 'remotedesktop-token')

	def load(self) -> str | None:
		try:
			with open(self.path, encoding='utf-8') as file:
				return file.read().strip() or None
		except OSError:
			return None

	def save(self, token: str | None):
		if not token:
			return
		os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
		fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
		with os.fdopen(fd, 'w', encoding='utf-8') as file:
			file.write(token)

	def clear(self):
		with suppress(OSError):
			os.unlink(self.path)


class _Portal:
	"""Minimal RemoteDesktop portal client on top of dbus-fast"""

	def __init__(self, bus: MessageBus, timeout: float):
		self.bus = bus
		self.timeout = timeout
		self.session: str | None = None
		self._pending: dict[str, asyncio.Future] = {}
		self.bus.add_message_handler(self._on_message)

	async def setup(self):
		await self._call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'AddMatch', 's',
			[f"type='signal',interface='{IFACE_REQUEST}',member='Response'"])

	def _on_message(self, msg: Message):
		if msg.message_type == MessageType.SIGNAL and msg.interface == IFACE_REQUEST \
				and msg.member == 'Response' and msg.path in self._pending:
			future = self._pending.pop(msg.path)
			if not future.done():
				future.set_result(msg.body)

	async def _call(self, dest, path, iface, member, signature='', body=None) -> Message:
		reply = await self.bus.call(Message(destination=dest, path=path, interface=iface, member=member,
			signature=signature, body=body or []))
		if reply is None or reply.message_type == MessageType.ERROR:
			error = reply.body[0] if reply and reply.body else ''
			raise AutotypeError(f'{member} failed: {reply.error_name if reply else "no reply"} {error}')
		return reply

	async def _request(self, member: str, signature: str, args: list, options: dict) -> dict:
		# subscribe before calling, the Response may arrive before the method reply
		token = 'kpxc' + secrets.token_hex(8)
		sender = self.bus.unique_name.lstrip(':').replace('.', '_')
		path = f'{PORTAL_PATH}/request/{sender}/{token}'
		future = asyncio.get_running_loop().create_future()
		self._pending[path] = future
		options = {**options, 'handle_token': Variant('s', token)}
		try:
			reply = await self._call(PORTAL_BUS, PORTAL_PATH, IFACE_REMOTE_DESKTOP, member, signature, [*args, options])
			handle = reply.body[0]
			if handle != path:  # old portals may use a different path
				self._pending[handle] = self._pending.pop(path, future)
			response, results = await asyncio.wait_for(future, self.timeout)
		finally:
			self._pending.pop(path, None)
		if response != 0:
			raise AutotypeError(f'{member} was not approved (response {response})')
		return {k: v.value for k, v in results.items()}

	async def start(self, restore_token: str | None) -> str | None:
		await self.setup()
		results = await self._request('CreateSession', 'a{sv}', [],
			{'session_handle_token': Variant('s', 'kpxc' + secrets.token_hex(8))})
		self.session = results['session_handle']
		options = {
			'types': Variant('u', DEVICE_KEYBOARD),
			'persist_mode': Variant('u', PERSIST_UNTIL_REVOKED),
		}
		if restore_token:
			options['restore_token'] = Variant('s', restore_token)
		await self._request('SelectDevices', 'oa{sv}', [self.session], options)
		results = await self._request('Start', 'osa{sv}', [self.session, ''], {})
		if not results.get('devices', 0) & DEVICE_KEYBOARD:
			raise AutotypeError('keyboard access was not granted')
		return results.get('restore_token')

	async def connect_to_eis(self) -> int:
		reply = await self._call(PORTAL_BUS, PORTAL_PATH, IFACE_REMOTE_DESKTOP, 'ConnectToEIS', 'oa{sv}', [self.session, {}])
		value = reply.body[0]
		# dbus-fast keeps the fd index in the body for low-level messages
		fd = reply.unix_fds[value] if reply.unix_fds and value < len(reply.unix_fds) else value
		return os.dup(fd)

	async def close(self):
		if self.session:
			with suppress(Exception):
				await self._call(PORTAL_BUS, self.session, IFACE_SESSION, 'Close')
			self.session = None


class _XkbResolver:
	"""Resolve characters to (evdev keycode, modifier keycodes) through an XKB keymap"""

	def __init__(self, keymap_string: bytes, group: int = 0):
		name = ctypes.util.find_library('xkbcommon') or 'libxkbcommon.so.0'
		xkb = ctypes.CDLL(name)
		xkb.xkb_context_new.restype = ctypes.c_void_p
		xkb.xkb_context_new.argtypes = [ctypes.c_int]
		xkb.xkb_keymap_new_from_string.restype = ctypes.c_void_p
		xkb.xkb_keymap_new_from_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
		for fn in ('xkb_keymap_min_keycode', 'xkb_keymap_max_keycode'):
			getattr(xkb, fn).restype = ctypes.c_uint32
			getattr(xkb, fn).argtypes = [ctypes.c_void_p]
		xkb.xkb_keymap_num_layouts_for_key.restype = ctypes.c_uint32
		xkb.xkb_keymap_num_layouts_for_key.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
		xkb.xkb_keymap_num_levels_for_key.restype = ctypes.c_uint32
		xkb.xkb_keymap_num_levels_for_key.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
		xkb.xkb_keymap_key_get_syms_by_level.restype = ctypes.c_int
		xkb.xkb_keymap_key_get_syms_by_level.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
			ctypes.c_uint32, ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32))]
		xkb.xkb_keymap_key_get_mods_for_level.restype = ctypes.c_size_t
		xkb.xkb_keymap_key_get_mods_for_level.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
			ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.c_size_t]
		xkb.xkb_keymap_mod_get_index.restype = ctypes.c_uint32
		xkb.xkb_keymap_mod_get_index.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
		xkb.xkb_utf32_to_keysym.restype = ctypes.c_uint32
		xkb.xkb_utf32_to_keysym.argtypes = [ctypes.c_uint32]
		xkb.xkb_keymap_unref.argtypes = [ctypes.c_void_p]
		xkb.xkb_context_unref.argtypes = [ctypes.c_void_p]
		self.xkb = xkb

		ctx = xkb.xkb_context_new(0)
		keymap = xkb.xkb_keymap_new_from_string(ctx, keymap_string.rstrip(b'\0'), 1, 0)
		if not keymap:
			xkb.xkb_context_unref(ctx)
			raise AutotypeError('could not parse the keymap sent by the compositor')
		try:
			self._build(keymap, group)
		finally:
			xkb.xkb_keymap_unref(keymap)
			xkb.xkb_context_unref(ctx)

	def _mod_bit(self, keymap, name: str) -> int:
		index = self.xkb.xkb_keymap_mod_get_index(keymap, name.encode())
		return 0 if index == 0xffffffff else 1 << index

	def _build(self, keymap, group: int):
		xkb = self.xkb
		shift = self._mod_bit(keymap, 'Shift')
		level3 = self._mod_bit(keymap, 'Mod5') | self._mod_bit(keymap, 'LevelThree')
		allowed = shift | level3

		def cost(keycode: int, mask: int) -> tuple:
			# X11 / Xwayland can't handle keycodes above 255, then prefer fewer modifiers
			return (keycode > 255, mask.bit_count(), keycode)

		# keysym -> (xkb keycode, mask), modifier keysym -> [evdev keycodes]
		table: dict[int, tuple[int, int]] = {}
		modifier_keys: dict[int, list[int]] = {}
		syms = ctypes.POINTER(ctypes.c_uint32)()
		masks = (ctypes.c_uint32 * 16)()
		for keycode in range(xkb.xkb_keymap_min_keycode(keymap), xkb.xkb_keymap_max_keycode(keymap) + 1):
			layouts = xkb.xkb_keymap_num_layouts_for_key(keymap, keycode)
			if layouts == 0:
				continue
			layout = group if group < layouts else 0
			for level in range(xkb.xkb_keymap_num_levels_for_key(keymap, keycode, layout)):
				count = xkb.xkb_keymap_key_get_syms_by_level(keymap, keycode, layout, level, ctypes.byref(syms))
				if count != 1:
					continue
				keysym = syms[0]
				n = xkb.xkb_keymap_key_get_mods_for_level(keymap, keycode, layout, level, masks, len(masks))
				candidates = [masks[i] for i in range(n) if masks[i] & ~allowed == 0]
				if not candidates:
					continue
				mask = min(candidates, key=lambda m: m.bit_count())
				if mask == 0 and keysym in (XK_Shift_L, XK_ISO_Level3_Shift, XK_Caps_Lock):
					modifier_keys.setdefault(keysym, []).append(keycode - XKB_EVDEV_OFFSET)
				known = table.get(keysym)
				if known is None or cost(keycode, mask) < cost(*known):
					table[keysym] = (keycode, mask)

		self.table = {sym: (kc - XKB_EVDEV_OFFSET, mask) for sym, (kc, mask) in table.items()}

		def modifier_key(keysym: int, preferred: int) -> int:
			# prefer the physical key (keymaps also contain virtual ones like <LVL3>)
			keys = modifier_keys.get(keysym, [])
			return preferred if preferred in keys or not keys else keys[0]

		self.shift_mask, self.level3_mask = shift, level3
		self.lock_mask = self._mod_bit(keymap, 'Lock')
		self.shift_key = modifier_key(XK_Shift_L, KEY_LEFTSHIFT)
		self.level3_key = modifier_key(XK_ISO_Level3_Shift, KEY_RIGHTALT)
		self.capslock_key = modifier_key(XK_Caps_Lock, KEY_CAPSLOCK)

	def keysym_for(self, char: str) -> int:
		if char == '\t':
			return XK_Tab
		if char in '\n\r':
			return XK_Return
		return self.xkb.xkb_utf32_to_keysym(ord(char))

	def resolve(self, text: str, max_keycode: int | None = None) -> list[tuple[int, list[int]]]:
		"""
		list of (evdev keycode, [modifier keycodes]); raises if a character can't be typed
		max_keycode limits the evdev keycodes (X11 keycodes = evdev + 8 can't exceed 255)
		"""
		result = []
		for char in text:
			entry = self.table.get(self.keysym_for(char))
			if entry is None or (max_keycode is not None and entry[0] > max_keycode):
				raise AutotypeError(f'character U+{ord(char):04X} is not available in the current keyboard layout')
			keycode, mask = entry
			mods = []
			if mask & self.shift_mask:
				mods.append(self.shift_key)
			if mask & self.level3_mask:
				mods.append(self.level3_key)
			result.append((keycode, mods))
		return result


class _EiConnection:
	"""libei sender wired into asyncio"""

	def __init__(self, fd: int, name: str):
		self.sender = ei.Sender.create_for_fd(fd, name=name)
		self.keyboard = None
		self.text = None
		self.locked_mods = 0
		self.group = 0
		self._changed = asyncio.Event()
		self._loop = asyncio.get_running_loop()
		self._loop.add_reader(self.sender.fd, self._dispatch)
		self._dispatch()

	def _dispatch(self):
		self.sender.dispatch()
		for event in self.sender.events:
			etype = event.event_type
			if etype is ei.EventType.SEAT_ADDED:
				wanted = tuple(c for c in (ei.DeviceCapability.KEYBOARD, getattr(ei.DeviceCapability, 'TEXT', None))
					if c is not None and c in event.seat.capabilities)
				if wanted:
					event.seat.bind(wanted)
			elif etype is ei.EventType.DEVICE_RESUMED:
				caps = event.device.capabilities
				if getattr(ei.DeviceCapability, 'TEXT', None) in caps:
					self.text = event.device
				if ei.DeviceCapability.KEYBOARD in caps:
					self.keyboard = event.device
			elif etype is ei.EventType.KEYBOARD_MODIFIERS:
				mods = event.keyboard_xkb_modifiers
				self.locked_mods, self.group = mods.locked, mods.group
			elif etype is ei.EventType.DISCONNECT:
				self.keyboard = self.text = None
		self._changed.set()

	async def wait_for_devices(self, timeout: float, text_grace: float = 0.2):
		deadline = self._loop.time() + timeout
		keyboard_since = None
		while True:
			if self.text is not None:
				return
			if self.keyboard is not None:
				keyboard_since = keyboard_since or self._loop.time()
				# keyboard is there, give a TEXT device a moment to show up as well
				if self._loop.time() - keyboard_since >= text_grace:
					return
			remaining = deadline - self._loop.time()
			if remaining <= 0:
				raise AutotypeError('the compositor did not provide a keyboard device')
			self._changed.clear()
			with suppress(asyncio.TimeoutError):
				await asyncio.wait_for(self._changed.wait(), min(remaining, text_grace))

	def close(self):
		with suppress(Exception):
			self._loop.remove_reader(self.sender.fd)
		with suppress(Exception):
			self.sender.disconnect()


def _key_sequence(resolver: _XkbResolver, keys: list[tuple[int, list[int]]], caps_locked: bool) -> list[list[tuple[int, bool]]]:
	"""(keycode, is_press) events grouped per typed character"""
	def tap(code):
		return [(code, True), (code, False)]

	sequence = []
	if caps_locked:
		# with caps lock on letters would come out inverted, toggle it off for the duration
		sequence.append(tap(resolver.capslock_key))
	for keycode, mods in keys:
		sequence.append([(m, True) for m in mods] + tap(keycode) + [(m, False) for m in reversed(mods)])
	if caps_locked:
		sequence.append(tap(resolver.capslock_key))
	return sequence


_X11_LIBRARIES = (
	('X11', 'libX11.so.6'),
	('Xtst', 'libXtst.so.6'),
	('xcb', 'libxcb.so.1'),
	('xkbcommon-x11', 'libxkbcommon-x11.so.0'),
	('xkbcommon', 'libxkbcommon.so.0'),
)


class _X11Keyboard:
	"""XTEST key events plus the server's XKB keymap via libxkbcommon-x11"""

	XKB_STATE_MODS_LOCKED = 1 << 2
	XKB_STATE_LAYOUT_EFFECTIVE = 1 << 7

	def __init__(self):
		x11, xtst, xcb, xkbx11, xkb = (ctypes.CDLL(_find_library(n, f)) for n, f in _X11_LIBRARIES)
		x11.XOpenDisplay.restype = ctypes.c_void_p
		x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
		x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
		x11.XFlush.argtypes = [ctypes.c_void_p]
		x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
		xtst.XTestQueryExtension.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_int)] * 4
		xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
		xcb.xcb_connect.restype = ctypes.c_void_p
		xcb.xcb_connect.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
		xcb.xcb_connection_has_error.argtypes = [ctypes.c_void_p]
		xcb.xcb_disconnect.argtypes = [ctypes.c_void_p]
		xkbx11.xkb_x11_setup_xkb_extension.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_int] + [ctypes.c_void_p] * 4
		xkbx11.xkb_x11_get_core_keyboard_device_id.argtypes = [ctypes.c_void_p]
		xkbx11.xkb_x11_get_core_keyboard_device_id.restype = ctypes.c_int32
		xkbx11.xkb_x11_keymap_new_from_device.restype = ctypes.c_void_p
		xkbx11.xkb_x11_keymap_new_from_device.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int]
		xkbx11.xkb_x11_state_new_from_device.restype = ctypes.c_void_p
		xkbx11.xkb_x11_state_new_from_device.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32]
		xkb.xkb_context_new.restype = ctypes.c_void_p
		xkb.xkb_context_new.argtypes = [ctypes.c_int]
		xkb.xkb_context_unref.argtypes = [ctypes.c_void_p]
		xkb.xkb_keymap_unref.argtypes = [ctypes.c_void_p]
		xkb.xkb_state_unref.argtypes = [ctypes.c_void_p]
		xkb.xkb_keymap_get_as_string.restype = ctypes.c_void_p
		xkb.xkb_keymap_get_as_string.argtypes = [ctypes.c_void_p, ctypes.c_int]
		xkb.xkb_state_serialize_layout.restype = ctypes.c_uint32
		xkb.xkb_state_serialize_layout.argtypes = [ctypes.c_void_p, ctypes.c_int]
		xkb.xkb_state_serialize_mods.restype = ctypes.c_uint32
		xkb.xkb_state_serialize_mods.argtypes = [ctypes.c_void_p, ctypes.c_int]
		self.x11, self.xtst, self.xcb, self.xkbx11, self.xkb = x11, xtst, xcb, xkbx11, xkb
		self.libc = ctypes.CDLL(None)
		self.libc.free.argtypes = [ctypes.c_void_p]

		self.display = x11.XOpenDisplay(None)
		if not self.display:
			raise AutotypeError('could not open the X display')
		dummy = [ctypes.c_int() for _ in range(4)]
		if not xtst.XTestQueryExtension(self.display, *(ctypes.byref(d) for d in dummy)):
			self.close()
			raise AutotypeError('the X server does not support the XTEST extension')

	def keymap(self) -> tuple[bytes, int, int]:
		"""(keymap as text, effective layout group, locked modifier mask)"""
		xcb, xkbx11, xkb = self.xcb, self.xkbx11, self.xkb
		conn = xcb.xcb_connect(None, None)
		ctx = keymap = state = None
		try:
			if not conn or xcb.xcb_connection_has_error(conn):
				raise AutotypeError('could not connect to the X server')
			if not xkbx11.xkb_x11_setup_xkb_extension(conn, 1, 0, 0, None, None, None, None):
				raise AutotypeError('the X server does not support the XKB extension')
			device = xkbx11.xkb_x11_get_core_keyboard_device_id(conn)
			if device < 0:
				raise AutotypeError('no core keyboard found')
			ctx = xkb.xkb_context_new(0)
			keymap = xkbx11.xkb_x11_keymap_new_from_device(ctx, conn, device, 0)
			state = keymap and xkbx11.xkb_x11_state_new_from_device(keymap, conn, device)
			if not keymap or not state:
				raise AutotypeError('could not read the keymap from the X server')
			raw = xkb.xkb_keymap_get_as_string(keymap, 1)
			try:
				data = ctypes.string_at(raw)
			finally:
				self.libc.free(raw)
			group = xkb.xkb_state_serialize_layout(state, self.XKB_STATE_LAYOUT_EFFECTIVE)
			locked = xkb.xkb_state_serialize_mods(state, self.XKB_STATE_MODS_LOCKED)
			return data, group, locked
		finally:
			if state:
				xkb.xkb_state_unref(state)
			if keymap:
				xkb.xkb_keymap_unref(keymap)
			if ctx:
				xkb.xkb_context_unref(ctx)
			if conn:
				xcb.xcb_disconnect(conn)

	def key(self, evdev_keycode: int, is_press: bool):
		self.xtst.XTestFakeKeyEvent(self.display, evdev_keycode + XKB_EVDEV_OFFSET, int(is_press), 0)

	def flush(self):
		self.x11.XFlush(self.display)

	def close(self):
		if self.display:
			self.x11.XSync(self.display, 0)
			self.x11.XCloseDisplay(self.display)
			self.display = None


class Autotype:

	def __init__(self, app_name: str, delay: float = 0.3, key_delay: float = 0.01, timeout: float = 120):
		self.app_name = app_name
		self.delay = delay
		self.key_delay = key_delay
		self.timeout = timeout
		self.tokens = _TokenStore(app_name)
		self._lock = asyncio.Lock()

	async def type(self, text: str):
		if not text:
			return
		match backend():
			case 'wayland':
				await self._type_wayland(text)
			case 'x11':
				await self._type_x11(text)
			case _:
				raise AutotypeError('auto-type needs libei on Wayland or the XTEST libraries on X11')

	async def _type_x11(self, text: str):
		async with self._lock:
			# let krunner close and the previous window regain focus
			await asyncio.sleep(self.delay)
			keyboard = _X11Keyboard()
			try:
				data, group, locked = keyboard.keymap()
				resolver = _XkbResolver(data, group)
				# resolve everything first, never type a secret partially
				keys = resolver.resolve(text, max_keycode=255 - XKB_EVDEV_OFFSET)
				for events in _key_sequence(resolver, keys, bool(locked & resolver.lock_mask)):
					for code, is_press in events:
						keyboard.key(code, is_press)
					keyboard.flush()
					await asyncio.sleep(self.key_delay)
			finally:
				keyboard.close()

	async def _type_wayland(self, text: str):
		async with self._lock:
			bus = await MessageBus(negotiate_unix_fd=True).connect()
			portal = _Portal(bus, self.timeout)
			connection = None
			try:
				try:
					token = await portal.start(self.tokens.load())
				except AutotypeError:
					# a stale token is rejected silently by most portals, but drop it either way
					self.tokens.clear()
					raise
				self.tokens.save(token)

				connection = _EiConnection(await portal.connect_to_eis(), self.app_name)
				await connection.wait_for_devices(timeout=5)

				# let krunner close and the previous window regain focus
				await asyncio.sleep(self.delay)

				if connection.text is not None:
					await self._type_text(connection.text, text)
				else:
					await self._type_keys(connection, text)
			finally:
				if connection:
					connection.close()
				await portal.close()
				bus.disconnect()

	async def _type_text(self, device, text: str):
		device.start_emulating()
		try:
			for char in text:
				device.text_utf8(char).frame()
				await asyncio.sleep(self.key_delay)
		finally:
			device.stop_emulating()

	async def _type_keys(self, connection: _EiConnection, text: str):
		device = connection.keyboard
		keymap = device.keymap
		if keymap is None:
			raise AutotypeError('the keyboard device has no keymap')
		with keymap.fd as file:
			data = file.read(keymap.size)
		resolver = _XkbResolver(data, connection.group)
		# resolve everything first, never type a secret partially
		keys = resolver.resolve(text)
		sequence = _key_sequence(resolver, keys, bool(connection.locked_mods & resolver.lock_mask))

		device.start_emulating()
		try:
			for events in sequence:
				for code, is_press in events:
					device.keyboard_key(code, is_press).frame()
				await asyncio.sleep(self.key_delay)
		finally:
			device.stop_emulating()
