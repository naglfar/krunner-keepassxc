# krunner-keepassxc

A small krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.
Requires xclip or xsel to be installed for copying to clipboard, keepass has to be configured for secret service access (in both general and database settings).
Transferring passwords through an encrypted session requires the python module cryptography to be installed, falls back on plaintext transmission.

## quick start using pip ##
this will pull the files and dependencies (dbus-python, cryptography) into your global python installation
```
$ sudo pip3 install https://github.com/naglfar/krunner-keepassxc/releases/download/1.0.0/krunner_keepassxc-1.0.0-py3-none-any.whl
see if it works:
$ python3 -m krunner_keepassxc_cli -l  # should list all the password labels in your database
$ python3 -m krunner_keepassxc_krunner  # will start the dbus service for communicating with krunner
```

## quick start using poetry ## 
```
$ git clone git@github.com:naglfar/krunner-keepassxc.git
$ cd krunner-keepassxc
$ poetry install
$ poetry run cli -l # should list all the password labels in your database
```

## installing the krunner plugin  ##
copy [install/krunner-keepassxc.desktop](install/krunner-keepassxc.desktop) to ~/.local/share/kservices5/  
after this krunner-keepassxc should already show up in krunner plugins but might require a reboot to actually work

## running the service in background / on startup ##
# via autostart
edit [install/krunner-keepassxc_autostart.desktop](install/krunner-keepassxc_autostart.desktop) to fit your scenario  
and copy to ~/.config/autostart
# via systemd
edit path or use python -m in [install/krunner-keepassxc_novenv.service](install/krunner-keepassxc_novenv.service)  
and copy to ~/.config/systemd/user/krunner-keepassxc.service
# via systemd as venv (poetry installation)
edit path in [install/krunner-keepassxc_venv.service](install/krunner-keepassxc_venv.service)  
and copy to ~/.config/systemd/user/krunner-keepassxc.service
```
$ systemctl --user enable krunner-keepassxc && systemctl --user start krunner-keepassxc
```
