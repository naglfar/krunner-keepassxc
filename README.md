# <img src="https://raw.githubusercontent.com/naglfar/krunner-keepassxc/master/logo.svg" width="64" height="64"/> krunner-keepassxc

A krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.

## Usage
You can install the plugin through the krunner settings dialog or alternatively find it on the [web store](https://store.kde.org/p/1414906/), download the archive, extract and run the install.sh, which should get everything up and running.

### Requirements:
- Python 3.6 or higher
- KeepassXC installed and configured for Freedesktop.org Secret Service access (See below)

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
- icon (default: object-unlock, you can find possible values in /usr/share/icons/<your theme>/)

The config file gets read on startup, which you can trigger manually by running `systemctl restart --user krunner-keepassxc.service`

### Other Information:
As this is a python application communicating with krunner through D-Bus it needs to be running constantly, for this purpose the install script will place the executable at ~/.local/bin/krunner-keepassxc (you can run this for the CLI) and place a systemd unit file at ~/.config/systemd/user/ to control it. If you're not using systemd a KDE autostart script will be created instead.

  
## more manual ways of getting started ##

### start using pyz file ###
Just download [krunner-keepassxc.pyz](https://github.com/naglfar/krunner-keepassxc/releases/download/1.7.0/krunner-keepassxc.pyz) and you're good to go!  
This is a fully self-contained Python zipapp with included dependencies (see [github.com/linkedin/shiv](https://github.com/linkedin/shiv))
```
$ ./krunner-keepassxc.pyz	# or do $ python krunner-keepassxc.pyz
```

### start using pip ###
this will pull the files and dependencies (dbus-python, cryptography) into your global python installation
```
$ sudo pip3 install https://github.com/naglfar/krunner-keepassxc/releases/download/1.7.0/krunner_-_keepassxc-1.7.0-py3-none-any.whl
# see if it works:
$ python3 -m krunner-keepassxc -l  # should list all the password labels in your database
$ python3 -m krunner-keepassxc run  # will start the dbus service for communicating with krunner
```

### using poetry ###
mostly for development
```
$ git clone git@github.com:naglfar/krunner-keepassxc.git
$ cd krunner-keepassxc
$ poetry install
$ poetry run -l # should list all the password labels in your database
```

### installing the krunner plugin  ###
copy [install/krunner-keepassxc.desktop](install/krunner-keepassxc.desktop) to ~/.local/share/kservices5/
after this krunner-keepassxc should already show up in krunner plugins but might require a reboot to actually work

### running the script in background / on startup ###
# via autostart
edit [install/krunner-keepassxc_autostart.desktop](install/krunner-keepassxc_autostart.desktop) and uncomment your scenario,
then copy to ~/.config/autostart/
# via systemd
edit [install/krunner-keepassxc.service](install/krunner-keepassxc.service) and uncomment your scenario,
then copy to ~/.config/systemd/user/
```
$ systemctl --user enable krunner-keepassxc && systemctl --user start krunner-keepassxc
```
