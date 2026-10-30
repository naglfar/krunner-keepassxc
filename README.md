# <img src="https://raw.githubusercontent.com/naglfar/krunner-keepassxc/master/logo.svg" width="64" height="64"/> krunner-keepassxc

A krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.

> :warning: with one of the newer versions (^2.7.1) keepassxc will turn off secret service integration until you disable kwallet. Either that or the newer versions of KDE plasma (^5.25) turn kwallet on if it used to be off. Not sure, but if the plugin suddenly stops working this might be the reason.

## Usage
You can install the plugin through the krunner settings dialog or alternatively find it on the [web store](https://store.kde.org/p/1414906/), download the archive, extract and run the `install.sh`, which should get everything up and running.

### Requirements:
- Python 3.14 (probably runs with 3.10+)
- KeepassXC installed and configured for Freedesktop.org Secret Service access (See below)
- recommended, Wayland: `wl-clipboard` >= 2.3.0, copied secrets are then marked as passwords (`wl-copy --sensitive`) and kept out of the Klipper history. Without it the plugin copies through Klipper's D-Bus interface, then **secrets end up in Klipper's history, which by default is also saved to disk**

### Enable Secret Service in KeepassXC:
* Open KeepassXC client
* Go to: Tools > Settings > Secret Service Integration
* Check "Enable KeepassXC Freedesktop.org Secret Service integration"
* for each used database:
  * Go to: Database > Database Settings > Secret Service integration
  * Select "Expose entries under this group"
  * Select the folder that you wish to make available through Secret Service (Select Root if you want to expose all)
  * Click OK

### Usage Instructions:
* Launch KRunner.
* Enter a search term from the title of the password entry you wish to obtain credentials for
* Mouse: can click on the entry you are looking for to copy the password to the clipboard.
* Mouse: can click on the icon to the right of the entry to copy the username.
* Keyboard: navigate to the entry you want by using the arrow keys.
* Keyboard: Press enter to copy the password to the clipboard
* Keyboard: Press shift + enter to copy the username to the clipboard.

### config file ##
On first start the plugin will create a config file with default values in `~/.config/krunner-keepassxc/config` (`~/.config` being $XDG_CONFIG_HOME) where you can add a few settings:
- trigger word (default: empty)
- max number of entries to show (default: 5)
- icon (default: object-unlock, you can find possible values in `/usr/share/icons/<your theme>/`)
- totp_as_extra_entry (true / false, default: true): if you have TOTP set up in any entries they will show up as separate result entries with an added TOTP to the name, if false you will instead get a secondary action icon to copy the TOTP. Though, due to krunner limitations this action has no keyboard shortcut and will show up for all entries, even for those without TOTP configured, thus not being the default.
- autotype (true / false, default: false): type the password / username / TOTP into the focused window instead of copying it to the clipboard, see below
- autotype_delay (milliseconds, default: 300): time to wait before typing, so krunner can close and the previous window gets the focus back
- clipboard_clear_delay (seconds, default: 10): empty the clipboard this many seconds after a value was copied, 0 disables it (see the warning below)
- idle_timeout (seconds, default: 600): exit the service after this many seconds without a krunner request, it gets started again automatically on the next request. 0 keeps it running once started. For development you can override it on the command line, e.g. `uv run runner --idle-timeout 0`.

> :warning: **The clipboard gets emptied `clipboard_clear_delay` seconds (default: 10) after copying a value, regardless of what it contains by then.** If you copy something else in the meantime, that gets cleared as well. Set `clipboard_clear_delay = 0` to disable this. Copying another value restarts the timer. When the value was copied through Klipper's D-Bus interface (no `wl-copy` >= 2.3.0 available), the clipboard is overwritten with a single space instead of being emptied, because Klipper restores its newest history entry (the copied value) as soon as the clipboard is empty; the value itself stays in Klipper's history.

Changes to the config file apply automatically on the next search, no restart needed. If the file can't be read (e.g. a syntax error), the previous settings stay in effect and a warning is logged (`journalctl --user -f`). Removing an option from the file resets it to its default, the option is added to the file again.

### Auto-type
With `autotype = true` the values are typed into the window that had the focus before krunner opened.

**Wayland** uses the XDG RemoteDesktop portal (keyboard only) and libei, so it needs:
- a Wayland session (Plasma 6, KWin provides EIS through xdg-desktop-portal-kde)
- the native `libei` library (Fedora/Arch: `libei`, Debian/Ubuntu: `libei1`) and `libxkbcommon`

The first time something gets typed the portal asks for permission to control the keyboard, the approval is remembered (restore token in `~/.local/state/krunner-keepassxc/remotedesktop-token`, delete it to be asked again). While typing, Plasma briefly shows its "remote control" indicator in the system tray.

If the compositor offers libei's text input (libei >= 1.6) the text is sent as characters, otherwise the characters are mapped to keys using the current keyboard layout; values containing characters that the layout can't produce are not typed at all.

**X11** sends the keys with the XTEST extension, no permission dialog involved. It needs `libX11`, `libXtst`, `libxcb` and `libxkbcommon-x11`, which are installed on practically every X11 Plasma desktop. The current keyboard layout (including layout switching) and caps lock are taken into account, characters the layout can't produce abort typing the same way as on Wayland.

If auto-type fails for any reason the value is copied to the clipboard instead.

### Other Information:
This is a python application communicating with krunner through D-Bus. It is started on demand by the D-Bus session bus (D-Bus activation) the first time krunner queries it, so no autostart entry or systemd unit is required. The install script places the executable at `~/.local/bin/krunner-keepassxc` (you can run this for the CLI) and a D-Bus service file at `~/.local/share/dbus-1/services/de.naglfar.krunner-keepassxc.service`. Older installations using a systemd user unit or an autostart entry are cleaned up by the install script.


## more manual ways of getting started ##

### start using built Niutka binary ###
Just download [krunner-keepassxc](https://github.com/naglfar/krunner-keepassxc/releases/latest/download/krunner-keepassxc) and you're good to go!
This is a fully self-contained binary with all dependencies (see [github.com/nuitka/nuitka](https://github.com/nuitka/nuitka))
```
$ ./krunner-keepassxc
```

### start using pip ###
this will pull the files and dependencies (dbus-fast, cryptography, …) into your global python installation
```
$ sudo pip3 install https://github.com/naglfar/krunner-keepassxc/releases/download/2.1.1/krunner_-_keepassxc-2.1.1-py3-none-any.whl
# see if it works:
$ python3 -m krunner_keepassxc -l  # should list all the password labels in your database
$ python3 -m krunner_keepassxc run  # will start the dbus service for communicating with krunner
```

### using uv ###
mostly for development
```
$ git clone git@github.com:naglfar/krunner-keepassxc.git
$ cd krunner-keepassxc
$ uv sync
$ uv run cli -l # should list all the password labels in your database
```

### installing the krunner plugin  ###
copy [`install/krunner-keepassxc.desktop`](install/krunner-keepassxc.desktop) to `~/.local/share/krunner/dbusplugins/` (`~/.local/share/kservices5/` for plasma5)
after this krunner-keepassxc should already show up in krunner plugins but might require a reboot to actually work

### starting the service on demand (D-Bus activation) ###
edit [`install/de.naglfar.krunner-keepassxc.service`](install/de.naglfar.krunner-keepassxc.service) and uncomment your scenario (`Exec` needs an absolute path),
then copy to `~/.local/share/dbus-1/services/`
```
$ mkdir -p ~/.local/share/dbus-1/services
$ cp install/de.naglfar.krunner-keepassxc.service ~/.local/share/dbus-1/services/
# let the session bus pick up the new file (usually happens automatically)
$ busctl --user call org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus ReloadConfig
```
The session bus will now start krunner-keepassxc as soon as krunner sends its first query.
