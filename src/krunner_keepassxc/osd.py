"""
Short on-screen messages through plasmashell's OSD
"""
from dbus_fast import Message, MessageFlag
from dbus_fast.aio import MessageBus


async def show_osd(bus: MessageBus, text: str, icon: str) -> None:
	"""show text and icon, without waiting for plasmashell; problems are only logged"""
	try:
		await bus.send(Message(
			destination='org.kde.plasmashell',
			path='/org/kde/osdService',
			interface='org.kde.osdService',
			member='showText',
			signature='ss',
			body=[icon, text],
			flags=MessageFlag.NO_REPLY_EXPECTED,
		))
	except Exception as e:  # noqa: BLE001 - feedback is optional, never break the krunner call
		print(f'could not show the OSD: {e!r}', flush=True)
