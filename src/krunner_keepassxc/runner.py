import asyncio
import time

from dbus_fast import Variant
from dbus_fast.aio import MessageBus
from dbus_fast.annotations import Annotated, DBusSignature, DBusStr, DBusVariant
from dbus_fast.service import ServiceInterface, dbus_method

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

	def __init__(self, config, bus):
		super().__init__(IFACE_KRUNNER)

		# self.check_config()
		self.config = config

		self.kp = KeepassPasswords(self.config, bus)
		self.cp = Clipboard()
		self.last_match = 0

	def copy_to_clipboard(self, string: str):
		if string:
			try:
				self.cp.copy(string)
			except NotImplementedError:
				print('neither xsel nor xclip seem to be installed', flush=True)
			except Exception as e:
				print(str(e), flush=True)

	@dbus_method()
	async def Actions(self) -> Annotated[
		list[tuple[str, str, str]],
		DBusSignature("a(sss)") # type: ignore[reportInvalidTypeForm]
	]:

		# populate entries to check for otp
		await self.kp.update_properties()

		actions = [
			('user', 'copy username', 'username-copy'),
		]

		# if otp entries exist and showing as extra entry is disabled, add an extra TOTP action
		if self.kp.otp and "totp_as_extra_entry" in self.config and self.config["totp_as_extra_entry"].lower() == 'false':
			actions.append(
				('totp', 'copy TOTP', 'accept_time_event'),
			)

		return actions

	@dbus_method()
	async def Match(self, query: DBusStr) -> Annotated[
		list[tuple[str, str, str, int, float, dict[str, Variant]]],
		DBusSignature("a(sssida{sv})") # type: ignore[reportInvalidTypeForm]
	]:
		# print(f"KRunner Query received: {query}")

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

		return matches

	@dbus_method()
	async def Run(self, match_id: DBusStr, action_id: DBusStr) -> DBusVariant:

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
				self.copy_to_clipboard(user)
			elif action_id == 'totp':
				totp = await self.kp.get_totp(match_id)
				if totp:
					self.copy_to_clipboard(totp)
			else:
				secret = await self.kp.get_secret(match_id)
				self.copy_to_clipboard(secret)

			# clear last_match to skip needless check_cache
			self.last_match = 0

		self.empty_action = ""

 		# Return empty/success tracking byte
		return Variant('y', 0)

class Runner:
	def __init__(self, config):
		self.config = config

	async def run(self):
		bus = await MessageBus().connect()

		runner = KeepassRunner(self.config, bus)
		bus.export(OBJ_PATH, runner)
		await bus.request_name(BUS_NAME)

		await asyncio.Event().wait()