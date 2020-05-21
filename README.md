# krunner-keepassxc

A small krunner plugin to copy keepassxc entries to clipboard using its Freedesktop.org Secret Service dbus integration.
Requires xclip or xsel to be installed for copying to clipboard, keepass has to be configured for secret service access (in both general and database settings).
Transferring passwords through an encrypted session requires the python module cryptography to be installed, falls back on plaintext transmission.

## quick start using poetry ## 
```
$ git clone git@github.com:naglfar/krunner-keepassxc.git
$ cd krunner-keepassxc
$ poetry install
edit path in install/krunner-keepassxc_venv.service and copy to ~/.config/systemd/user/krunner-keepassxc.service
copy install/krunner-keepassxc.desktop to ~/.local/share/kservices5/
$ systemctl --user enable krunner-keepassxc && systemctl --user start krunner-keepassxc
krunner-keepassxc should already show up in krunner plugins but might require a reboot to actually work
```
