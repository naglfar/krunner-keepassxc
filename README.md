# krunner-keepassxc

A small krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.
Basically, type something into krunner and the plugin will suggest matching keepassxc entries to copy.
Requires xclip or xsel to be installed for copying to clipboard, keepass has to be configured for secret service access (in both general and database settings).
Requires at least Python3.5, running the .pyz file requires python 3.6.

## quick start using pex or pyz file ##
Just download [krunner-keepassxc.pex](https://github.com/naglfar/krunner-keepassxc/releases/download/1.3.0/krunner-keepassxc.pex) or [krunner-keepassxc.pyz](https://github.com/naglfar/krunner-keepassxc/releases/download/1.3.0/krunner-keepassxc.pyz) and you're good to go!  
They are executable files you can just run
```
$ ./krunner-keepassxc.pex	# or do $ python krunner-keepassxc.pex
$ ./krunner-keepassxc.pyz	# or do $ python krunner-keepassxc.pyz
```

## quick start using pip ##
this will pull the files and dependencies (dbus-python, cryptography) into your global python installation
```
$ sudo pip3 install https://github.com/naglfar/krunner-keepassxc/releases/download/1.3.0/krunner_-_keepassxc-1.3.0-py3-none-any.whl
# see if it works:
$ python3 -m krunner-keepassxc cli -l  # should list all the password labels in your database
$ python3 -m krunner-keepassxc  # will start the dbus service for communicating with krunner
```

## using poetry ## 
```
$ git clone git@github.com:naglfar/krunner-keepassxc.git
$ cd krunner-keepassxc
$ poetry install
$ poetry run cli -l # should list all the password labels in your database
```

## installing the krunner plugin  ##
copy [install/krunner-keepassxc.desktop](install/krunner-keepassxc.desktop) to ~/.local/share/kservices5/  
after this krunner-keepassxc should already show up in krunner plugins but might require a reboot to actually work

## running the script in background / on startup ##
# via autostart
edit [install/krunner-keepassxc_autostart.desktop](install/krunner-keepassxc_autostart.desktop) and uncomment your scenario,  
then copy to ~/.config/autostart/
# via systemd
edit [install/krunner-keepassxc.service](install/krunner-keepassxc.service) and uncomment your scenario,  
then copy to ~/.config/systemd/user/
```
$ systemctl --user enable krunner-keepassxc && systemctl --user start krunner-keepassxc
```
