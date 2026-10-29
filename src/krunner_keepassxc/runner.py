import asyncio
import sys
import time

from dbus_fast import DBusError, NameFlag, RequestNameReply, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.annotations import Annotated, DBusSignature, DBusStr, DBusVariant
from dbus_fast.service import ServiceInterface, dbus_method

from .autotype import Autotype, AutotypeError
from .autotype import is_available as autotype_available
from .clipboard import Clipboard
from .keepass import KeepassPasswords

BUS_NAME = "de.naglfar.krunner-keepassxc"
OBJ_PATH="/krunner"
IFACE_KRUNNER="org.kde.krunner1"

class KeepassRunner(ServiceInterface):

	app_name = "krunner-keepassxc"

	kp: KeepassPasswords
	cp: Clipboard
	empty_action: str = ""
	last_match: float

	def __init__(self, config, bus, on_activity=None):
		super().__init__(IFACE_KRUNNER)

		# self.check_config()
		self.config = config
		# callback invoked on every incoming krunner call (used for the idle timeout)
		self.on_activity = on_activity

		self.kp = KeepassPasswords(self.config, bus)
		self.cp = Clipboard()
		self.last_match = 0

		self.autotype: Autotype | None = None
		if str(self.config.get('autotype', 'false')).lower() == 'true':
			if autotype_available():
				self.autotype = Autotype(self.app_name, delay=int(self.config.get('autotype_delay', 300)) / 1000)
			else:
				print('autotype enabled but not available (needs libei on Wayland or libXtst on X11), using the clipboard', flush=True)
		self._tasks: set[asyncio.Task] = set()
		self._clear_task: asyncio.Task | None = None
		# heading of the result group in krunner, overrides the Name of the .desktop file
		self.category = 'KeePassXC: auto-type' if self.autotype else 'KeePassXC: copy to clipboard'

	@property
	def busy(self) -> bool:
		"""background work still pending (auto-type, clearing the clipboard)"""
		return bool(self._tasks)

	def _touch(self):
		if self.on_activity:
			self.on_activity()

	def copy_to_clipboard(self, string: str):
		if string:
			try:
				self.cp.copy(string)
			except NotImplementedError:
				print('neither xsel nor xclip seem to be installed', flush=True)
				return
			except Exception as e:
				print(str(e), flush=True)
				return
			self._schedule_clipboard_clear()

	def _schedule_clipboard_clear(self):
		try:
			delay = int(self.config.get('clipboard_clear_delay', 10))
		except (TypeError, ValueError):
			delay = 10
		if delay <= 0:
			return
		# the delay always counts from the latest copy
		if self._clear_task is not None:
			self._clear_task.cancel()
		# kept in _tasks, so the idle timeout doesn't end the service before clearing
		task = asyncio.create_task(self._clear_clipboard_later(delay))
		self._clear_task = task
		self._tasks.add(task)
		task.add_done_callback(self._tasks.discard)

	async def _clear_clipboard_later(self, delay: int):
		await asyncio.sleep(delay)
		self._clear_task = None
		try:
			self.cp.clear()
		except Exception as e:  # noqa: BLE001 - only log, there is nobody to report to
			print(f'could not clear the clipboard: {e!r}', flush=True)

	def output(self, string: str):
		"""auto-type the value if enabled, otherwise copy it to the clipboard"""
		if not string:
			return
		if self.autotype is None:
			self.copy_to_clipboard(string)
			return
		# don't block the D-Bus reply, krunner has to close before we can type
		task = asyncio.create_task(self._autotype(string))
		self._tasks.add(task)
		task.add_done_callback(self._tasks.discard)

	async def _autotype(self, string: str):
		try:
			await self.autotype.type(string)
		except (AutotypeError, OSError) as e:
			print(f'autotype failed, copying to clipboard instead: {e}', flush=True)
			self.copy_to_clipboard(string)
		except Exception as e:  # noqa: BLE001 - never lose the value because of a libei/portal issue
			print(f'autotype failed unexpectedly, copying to clipboard instead: {e!r}', flush=True)
			self.copy_to_clipboard(string)

	@dbus_method()
	async def Actions(self) -> Annotated[
		list[tuple[str, str, str]],
		DBusSignature("a(sss)") # type: ignore[reportInvalidTypeForm]
	]:
		self._touch()

		# populate entries to check for otp
		await self.kp.update_properties()

		verb = 'type' if self.autotype else 'copy'
		actions = [
			('user', f'{verb} username', 'username-copy'),
		]

		# if otp entries exist and showing as extra entry is disabled, add an extra TOTP action
		if self.kp.otp and "totp_as_extra_entry" in self.config and self.config["totp_as_extra_entry"].lower() == 'false':
			actions.append(
				('totp', f'{verb} TOTP', 'accept_time_event'),
			)

		return actions

	@dbus_method()
	async def Match(self, query: DBusStr) -> Annotated[
		list[tuple[str, str, str, int, float, dict[str, Variant]]],
		DBusSignature("a(sssida{sv})") # type: ignore[reportInvalidTypeForm]
	]:
		# print(f"KRunner Query received: {query}")
		self._touch()

		matches:list = []

		if len(query) > 2 and query.startswith(self.config['trigger']):

			query = query[len(self.config['trigger']):].strip()

			if not self.cp.can_clip:
				self.cp.check_executables()

			if not self.cp.can_clip:
				matches = [
					('', "Neither xsel nor xclip installed", self.config['icon'], 100, 0.1, {})
				]

			elif len(await self.kp.get_entries()) == 0:
				if not self.kp.is_keepass_installed():
					matches = [
						('', "KeepassXC does not seem to be installed", self.config['icon'], 100, 0.1, {})
					]
				elif not self.kp.BUS_NAME:
					matches = [
						('', "DBUS bus name not found", self.config['icon'], 100, 0.1, {})
					]
				else:
					# no passwords found, show open keepass message
					matches = [
						('', "No passwords or database locked", self.config['icon'], 100, 0.1, { 'subtext': Variant('s', 'Open KeepassXC') })
					]
					self.empty_action = 'open-keepassxc'
			else:
				# find entries that contain the query, Path attribute contains keepass group name
				# TODO: maybe search through additional attributes aswell?
				entries = [e for e in await self.kp.get_entries() if any([
					all(x in e["attributes"]["Path"].lower() for x in query.lower().split(' ')),
					all(x in e["attributes"]["URL"].lower() for x in query.lower().split(' ')),
					all(x in e["attributes"]["UserName"].lower() for x in query.lower().split(' ')),
				])]

				# sort entries where the label starts with the query to the top
				# sort entries containing the query in the label over path next
				# everything else comes after
				# [print(e["label"]) for e in entries]
				entries.sort(key=lambda entry: (
						not entry["label"].lower().startswith(query.lower()),
						not query.lower() in entry["label"].lower(),
						entry["label"]
					)
				)

				# max entries
				entries = entries[:self.config['max_entries']]

				matches = [
				#	data, display text, icon, type (Plasma::QueryType), relevance (0-1), properties (subtext, category and urls)
					(
						entry["path"],
						entry["label"],
						self.config['icon'],
						100,
						1 - (i * 0.1),
						{
							'subtext': Variant('s', await self.kp.get_username(entry["path"]))
						}
					) for i, entry in enumerate(entries)
				]

				self.last_match = time.time()

		# same category for all results (including hints), otherwise they end up in separate groups
		return [(*match[:5], {**match[5], 'category': Variant('s', self.category)}) for match in matches]

	@dbus_method()
	async def Run(self, match_id: DBusStr, action_id: DBusStr) -> DBusVariant:
		self._touch()

		# matchId is data from Match, actionId is secondary action or empty for primary
		if len(match_id) == 0:
			# empty match_id means error of some kind
			if self.empty_action == 'open-keepassxc':
				self.kp.open_keepass()
		else:

			# forcing action for specific entries (i.e. TOTP)
			split_match = match_id.split(':')
			if len(split_match) > 1:
				match_id = split_match[0]
				action_id = split_match[1]

			if action_id == 'user':
				user = await self.kp.get_username(match_id)
				self.output(user)
			elif action_id == 'totp':
				totp = await self.kp.get_totp(match_id)
				if totp:
					self.output(totp)
			else:
				secret = await self.kp.get_secret(match_id)
				self.output(secret)

			# clear last_match to skip needless check_cache
			self.last_match = 0

		self.empty_action = ""

 		# Return empty/success tracking byte
		return Variant('y', 0)

class Runner:
	"""
	D-Bus service for krunner.

	The process is meant to be started on demand by the D-Bus daemon (see the
	de.naglfar.krunner-keepassxc.service activation file) as soon as krunner
	calls the runner for the first time. If ``idle_timeout`` (seconds) is set
	to a value > 0 the process releases its bus name and exits after that time
	without any krunner request (and no auto-type still running); the next
	request simply activates it again. ``run --idle-timeout 0`` keeps it running.
	"""

	def __init__(self, config):
		self.config = config
		self._idle_handle: asyncio.TimerHandle | None = None
		self._stop: asyncio.Event | None = None
		self._runner: KeepassRunner | None = None

	def _idle_timeout(self) -> int:
		try:
			return max(0, int(self.config.get('idle_timeout', 0)))
		except (TypeError, ValueError):
			return 0

	def _reset_idle_timer(self):
		timeout = self._idle_timeout()
		if timeout <= 0 or self._stop is None:
			return
		if self._idle_handle:
			self._idle_handle.cancel()
		self._idle_handle = asyncio.get_running_loop().call_later(timeout, self._on_idle)

	def _on_idle(self):
		if self._runner is not None and self._runner.busy:
			# e.g. auto-type waiting for the portal's consent dialog, check again later
			self._idle_handle = asyncio.get_running_loop().call_later(5, self._on_idle)
			return
		if self._stop is not None:
			self._stop.set()

	async def run(self):
		bus = await MessageBus().connect()

		runner = KeepassRunner(self.config, bus, on_activity=self._reset_idle_timer)
		self._runner = runner
		bus.export(OBJ_PATH, runner)

		reply = await bus.request_name(BUS_NAME, NameFlag.DO_NOT_QUEUE)
		if reply not in (RequestNameReply.PRIMARY_OWNER, RequestNameReply.ALREADY_OWNER):
			bus.disconnect()
			sys.exit(f'{BUS_NAME} is already owned by another process, exiting')

		self._stop = asyncio.Event()
		self._reset_idle_timer()

		stop_task = asyncio.create_task(self._stop.wait())
		disconnect_task = asyncio.create_task(bus.wait_for_disconnect())
		try:
			await asyncio.wait({stop_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED)
		finally:
			for task in (stop_task, disconnect_task):
				task.cancel()
			if self._idle_handle:
				self._idle_handle.cancel()

		if disconnect_task.done() and not disconnect_task.cancelled() and disconnect_task.exception():
			print(f'D-Bus connection lost: {disconnect_task.exception()}', file=sys.stderr, flush=True)

		if bus.connected:
			# release the name first so the next krunner call triggers a fresh activation
			try:
				await bus.release_name(BUS_NAME)
			except DBusError as e:
				print(f'could not release {BUS_NAME}: {e}', file=sys.stderr, flush=True)
			bus.disconnect()
